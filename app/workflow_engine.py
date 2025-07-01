import asyncio
import json
import yaml
import sys
import os
from typing import Dict, Any, List
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .models import WorkflowDefinition, WorkflowStatus, WorkflowStep, WorkflowControlRequest
    from .database import Database
    from .connectors.base import BaseConnector
    from .connectors.delay import DelayConnector
    from .connectors.webhook import WebhookConnector
except ImportError:
    # Fallback for direct execution
    from app.models import WorkflowDefinition, WorkflowStatus, WorkflowControlRequest
    from app.database import Database
    from app.connectors.base import BaseConnector
    from app.connectors.delay import DelayConnector
    from app.connectors.webhook import WebhookConnector

class WorkflowEngine:
    def __init__(self, database: Database):
        self.database = database
        self.connectors = {
            "delay": DelayConnector,
            "webhook": WebhookConnector
        }
        self.active_workflows = {}  # Track active workflows for pause/stop
    
    def register_connector(self, name: str, connector_class):
        """Register a new connector type"""
        self.connectors[name] = connector_class
    
    async def load_workflow_definition(self, workflow_name: str) -> WorkflowDefinition:
        """Load workflow definition from YAML file"""
        workflow_path = Path(f"workflows/{workflow_name}.yaml")
        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow {workflow_name} not found")
        
        with open(workflow_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return WorkflowDefinition(**data)
    
    async def check_workflow_status(self, run_id: int) -> WorkflowStatus:
        """Check current workflow status from database"""
        run = await self.database.get_workflow_run(run_id)
        return run.status if run else WorkflowStatus.STOPPED
    
    async def retry_step(self, run_id: int, step_index: int, step: WorkflowStep, context: Dict[str, Any], logs: List[str], max_retries: int = 3):
        """Retry a failed step with exponential backoff"""
        for attempt in range(max_retries):
            # Check if workflow was stopped/paused during retry
            current_status = await self.check_workflow_status(run_id)
            if current_status in [WorkflowStatus.STOPPED, WorkflowStatus.PAUSED]:
                logs.append(f"Step {step_index + 1} retry cancelled due to workflow {current_status.value}")
                return None
            
            if attempt > 0:
                # Exponential backoff: 2^attempt seconds
                delay = 2 ** attempt
                logs.append(f"Step {step_index + 1} retry {attempt + 1}/{max_retries} in {delay}s...")
                await asyncio.sleep(delay)
                
                # Update status to retrying
                await self.database.update_workflow_run(
                    run_id, WorkflowStatus.RETRYING, logs, current_step=step_index
                )
            
            # Get connector and execute
            connector_class = self.connectors[step.type]
            connector = connector_class(step.config)
            
            result = await connector.execute(context)
            
            if result.success:
                logs.append(f"Step {step_index + 1} succeeded on retry {attempt + 1}")
                return result
            else:
                logs.append(f"Step {step_index + 1} retry {attempt + 1} failed: {result.message}")
        
        return None  # All retries failed
    
    async def execute_workflow(self, run_id: int, workflow_name: str, trigger_payload: Dict[str, Any]):
        """Execute a workflow with pause/stop/retry support"""
        logs = [f"Starting workflow: {workflow_name}"]
        
        # Add to active workflows for control
        self.active_workflows[run_id] = {
            "status": "running",
            "current_step": 0
        }
        
        try:
            # Load workflow definition
            workflow_def = await self.load_workflow_definition(workflow_name)
            
            # Get workflow run info for retry settings
            run = await self.database.get_workflow_run(run_id)
            max_retries = run.max_retries if run else 3
            
            # Initialize context with trigger payload
            context = {
                "trigger": trigger_payload,
                "run_id": run_id,
                "workflow_name": workflow_name
            }
            
            # Execute each step
            for i, step in enumerate(workflow_def.steps):
                # Check workflow status before each step
                current_status = await self.check_workflow_status(run_id)
                
                if current_status == WorkflowStatus.STOPPED:
                    logs.append(f"Workflow stopped at step {i + 1}")
                    break
                elif current_status == WorkflowStatus.PAUSED:
                    logs.append(f"Workflow paused at step {i + 1}")
                    await self.database.update_workflow_run(
                        run_id, WorkflowStatus.PAUSED, logs, current_step=i
                    )
                    # Wait for resume (this is simplified - in production you'd use a proper queue system)
                    while await self.check_workflow_status(run_id) == WorkflowStatus.PAUSED:
                        await asyncio.sleep(1)
                    
                    # Check if it was resumed or stopped
                    current_status = await self.check_workflow_status(run_id)
                    if current_status == WorkflowStatus.STOPPED:
                        logs.append(f"Workflow stopped during pause at step {i + 1}")
                        break
                    else:
                        logs.append(f"Workflow resumed at step {i + 1}")
                
                # Update current step
                self.active_workflows[run_id]["current_step"] = i
                
                step_log = f"Executing step {i + 1}: {step.type}"
                logs.append(step_log)
                
                # Get connector class
                if step.type not in self.connectors:
                    raise ValueError(f"Unknown connector type: {step.type}")
                
                connector_class = self.connectors[step.type]
                connector = connector_class(step.config)
                
                # Execute step with timeout if specified
                try:
                    if hasattr(step, 'timeout_seconds') and step.timeout_seconds:
                        result = await asyncio.wait_for(
                            connector.execute(context), 
                            timeout=step.timeout_seconds
                        )
                    else:
                        result = await connector.execute(context)
                except asyncio.TimeoutError:
                    result = type('Result', (), {
                        'success': False, 
                        'message': f'Step timed out after {step.timeout_seconds}s',
                        'data': {}
                    })()
                
                if result.success:
                    logs.append(f"Step {i + 1} succeeded: {result.message}")
                    # Add step result to context for next steps
                    context[f"step_{i + 1}"] = result.data
                else:
                    logs.append(f"Step {i + 1} failed: {result.message}")
                    
                    # Check if we should retry this step
                    should_retry = getattr(step, 'retry_on_failure', True)
                    if should_retry and max_retries > 0:
                        logs.append(f"Attempting to retry step {i + 1}...")
                        retry_result = await self.retry_step(i, step, context, logs, max_retries)
                        
                        if retry_result and retry_result.success:
                            context[f"step_{i + 1}"] = retry_result.data
                            continue
                    
                    # Step failed after retries
                    await self.database.update_workflow_run(
                        run_id, WorkflowStatus.FAILED, logs, current_step=i
                    )
                    return
            
            # Check final status
            final_status = await self.check_workflow_status(run_id)
            if final_status == WorkflowStatus.STOPPED:
                logs.append("Workflow was stopped")
            elif final_status == WorkflowStatus.PAUSED:
                logs.append("Workflow ended in paused state")
            else:
                logs.append("Workflow completed successfully")
                await self.database.update_workflow_run(
                    run_id, WorkflowStatus.SUCCEEDED, logs
                )
            
        except Exception as e:
            logs.append(f"Workflow failed with error: {str(e)}")
            await self.database.update_workflow_run(
                run_id, WorkflowStatus.FAILED, logs
            )
        finally:
            # Remove from active workflows
            self.active_workflows.pop(run_id, None)