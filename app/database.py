import json
import sys
import os
from typing import List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, desc, text

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .models import Base, WorkflowRun, WorkflowStatus
except ImportError:
    # Fallback for direct execution
    from app.models import Base, WorkflowRun, WorkflowStatus

class Database:
    def __init__(self, database_url: str = "sqlite+aiosqlite:///./workflows.db"):
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            # Check if we need to migrate existing tables
            await self._migrate_schema_if_needed(conn)
    
    async def _migrate_schema_if_needed(self, conn):
        """Add missing columns to existing tables"""
        try:
            # Check if new columns exist, if not add them
            result = await conn.execute(text("PRAGMA table_info(workflow_runs)"))
            columns = [row[1] for row in result.fetchall()]
            
            migrations_needed = []
            if 'retry_count' not in columns:
                migrations_needed.append("ALTER TABLE workflow_runs ADD COLUMN retry_count INTEGER DEFAULT 0")
            if 'max_retries' not in columns:
                migrations_needed.append("ALTER TABLE workflow_runs ADD COLUMN max_retries INTEGER DEFAULT 3")
            if 'current_step' not in columns:
                migrations_needed.append("ALTER TABLE workflow_runs ADD COLUMN current_step INTEGER DEFAULT 0")
            
            # Execute migrations
            for migration in migrations_needed:
                await conn.execute(text(migration))
                print(f"✅ Applied migration: {migration}")
            
            if migrations_needed:
                print(f"🔄 Database schema updated with {len(migrations_needed)} new columns")
            
        except Exception as e:
            print(f"⚠️  Migration warning: {e}")
            print("💡 If you continue to see errors, delete 'workflows.db' and restart the server")
    
    async def create_workflow_run(
        self, 
        workflow_name: str, 
        trigger_payload: dict,
        max_retries: int = 3
    ) -> WorkflowRun:
        async with self.async_session() as session:
            run = WorkflowRun(
                workflow_name=workflow_name,
                trigger_payload=json.dumps(trigger_payload),
                logs=json.dumps([]),
                max_retries=max_retries
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run
    
    async def update_workflow_run(
        self, 
        run_id: int, 
        status: WorkflowStatus, 
        logs: List[str],
        retry_count: int = None,
        current_step: int = None
    ):
        async with self.async_session() as session:
            run = await session.get(WorkflowRun, run_id)
            if run:
                run.status = status
                run.logs = json.dumps(logs)
                if retry_count is not None:
                    run.retry_count = retry_count
                if current_step is not None:
                    run.current_step = current_step
                await session.commit()
    
    async def pause_workflow(self, run_id: int) -> bool:
        """Pause a workflow"""
        async with self.async_session() as session:
            run = await session.get(WorkflowRun, run_id)
            if run and run.status in [WorkflowStatus.STARTED, WorkflowStatus.RETRYING]:
                run.status = WorkflowStatus.PAUSED
                await session.commit()
                return True
            return False
    
    async def stop_workflow(self, run_id: int) -> bool:
        """Stop a workflow permanently"""
        async with self.async_session() as session:
            run = await session.get(WorkflowRun, run_id)
            if run and run.status != WorkflowStatus.STOPPED:
                run.status = WorkflowStatus.STOPPED
                await session.commit()
                return True
            return False
    
    async def resume_workflow(self, run_id: int) -> bool:
        """Resume a paused workflow"""
        async with self.async_session() as session:
            run = await session.get(WorkflowRun, run_id)
            if run and run.status == WorkflowStatus.PAUSED:
                run.status = WorkflowStatus.STARTED
                await session.commit()
                return True
            return False
    
    async def get_workflow_run(self, run_id: int) -> Optional[WorkflowRun]:
        async with self.async_session() as session:
            return await session.get(WorkflowRun, run_id)
    
    async def get_workflow_runs(self, limit: int = 100) -> List[WorkflowRun]:
        async with self.async_session() as session:
            stmt = select(WorkflowRun).order_by(desc(WorkflowRun.created_at)).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()