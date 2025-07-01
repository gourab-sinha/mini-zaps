import asyncio
import sys
import os
from typing import List
from fastapi import FastAPI, HTTPException, BackgroundTasks

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .models import TriggerRequest, WorkflowRunResponse, WorkflowStatus, WorkflowControlRequest
    from .database import Database
    from .workflow_engine import WorkflowEngine
except ImportError:
    # Fallback for direct execution
    from app.models import TriggerRequest, WorkflowRunResponse, WorkflowStatus
    from app.database import Database
    from app.workflow_engine import WorkflowEngine

app = FastAPI(title="Mini-Zaps Workflow Builder", version="0.1.0")
database = Database()
workflow_engine = WorkflowEngine(database)

@app.on_event("startup")
async def startup_event():
    try:
        await database.init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise

@app.post("/api/trigger", response_model=WorkflowRunResponse)
async def trigger_workflow(
    request: TriggerRequest,
    background_tasks: BackgroundTasks
):
    """Trigger a workflow execution"""
    try:
        # Create workflow run record
        run = await database.create_workflow_run(
            request.workflow_name, 
            request.payload,
            request.max_retries
        )
        
        # Start workflow execution in background
        background_tasks.add_task(
            workflow_engine.execute_workflow,
            run.id,
            request.workflow_name,
            request.payload
        )
        
        return WorkflowRunResponse(
            id=run.id,
            workflow_name=run.workflow_name,
            status=run.status,
            retry_count=run.retry_count,
            max_retries=run.max_retries,
            current_step=run.current_step,
            created_at=run.created_at,
            updated_at=run.updated_at
        )
        
    except FileNotFoundError as e:
        print(f"❌ Workflow not found: {e}")
        raise HTTPException(status_code=404, detail="Workflow not found")
    except Exception as e:
        print(f"❌ Error triggering workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/runs/{run_id}/control")
async def control_workflow(run_id: int, request: WorkflowControlRequest):
    """Control workflow execution (pause, stop, resume)"""
    try:
        action = request.action.lower()
        
        if action == "pause":
            success = await database.pause_workflow(run_id)
            message = "Workflow paused" if success else "Could not pause workflow"
        elif action == "stop":
            success = await database.stop_workflow(run_id)
            message = "Workflow stopped" if success else "Could not stop workflow"
        elif action == "resume":
            success = await database.resume_workflow(run_id)
            if success:
                # Get the workflow info to resume execution
                run = await database.get_workflow_run(run_id)
                # Note: In production, you'd use a proper queue system to resume
                message = "Workflow resumed (will continue from current step)"
            else:
                message = "Could not resume workflow"
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'pause', 'stop', or 'resume'")
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"success": True, "message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error controlling workflow {run_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/runs/{run_id}")
async def get_workflow_run(run_id: int):
    """Get workflow run status and logs"""
    try:
        run = await database.get_workflow_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        
        import json
        return {
            "id": run.id,
            "workflow_name": run.workflow_name,
            "status": run.status,
            "retry_count": run.retry_count,
            "max_retries": run.max_retries,
            "current_step": run.current_step,
            "logs": json.loads(run.logs) if run.logs else [],
            "created_at": run.created_at,
            "updated_at": run.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting workflow run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/runs")
async def list_workflow_runs(limit: int = 100):
    """List recent workflow runs"""
    try:
        runs = await database.get_workflow_runs(limit)
        return [
            WorkflowRunResponse(
                id=run.id,
                workflow_name=run.workflow_name,
                status=run.status,
                retry_count=run.retry_count,
                max_retries=run.max_retries,
                current_step=run.current_step,
                created_at=run.created_at,
                updated_at=run.updated_at
            )
            for run in runs
        ]
    except Exception as e:
        print(f"❌ Error listing workflow runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/active")
async def list_active_workflows():
    """List currently active workflows"""
    try:
        return {
            "active_workflows": workflow_engine.active_workflows,
            "count": len(workflow_engine.active_workflows)
        }
    except Exception as e:
        print(f"❌ Error listing active workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/connectors")
async def list_connectors():
    """List available connector types and their schemas"""
    try:
        return {
            name: connector_class.get_config_schema()
            for name, connector_class in workflow_engine.connectors.items()
        }
    except Exception as e:
        print(f"❌ Error listing connectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Mini-Zaps Workflow Builder API", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        from sqlalchemy import text
        async with database.async_session() as session:
            await session.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "database": "connected",
            "connectors": list(workflow_engine.connectors.keys())
        }
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Mini-Zaps Workflow Builder...")
    uvicorn.run(app, host="0.0.0.0", port=8000)