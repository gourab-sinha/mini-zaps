from enum import Enum
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class WorkflowStatus(str, Enum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PAUSED = "paused"
    STOPPED = "stopped"
    RETRYING = "retrying"

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_name = Column(String, index=True)
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.STARTED)
    trigger_payload = Column(Text)  # JSON string
    logs = Column(Text)  # JSON string
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    current_step = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# Pydantic models for API
class TriggerRequest(BaseModel):
    workflow_name: str
    payload: Dict[str, Any]
    max_retries: int = 3

class WorkflowStep(BaseModel):
    type: str
    config: Dict[str, Any]
    retry_on_failure: bool = True
    timeout_seconds: Optional[int] = None

class WorkflowDefinition(BaseModel):
    name: str
    steps: List[WorkflowStep]
    global_retry_policy: Dict[str, Any] = {}

class WorkflowRunResponse(BaseModel):
    id: int
    workflow_name: str
    status: WorkflowStatus
    retry_count: int
    max_retries: int
    current_step: int
    created_at: datetime
    updated_at: datetime

class WorkflowControlRequest(BaseModel):
    action: str  # "pause", "stop", "resume"