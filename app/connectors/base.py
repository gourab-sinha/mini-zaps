from abc import ABC, abstractmethod
from typing import Dict, Any, List

class ConnectorResult:
    def __init__(self, success: bool, message: str, data: Dict[str, Any] = None):
        self.success = success
        self.message = message
        self.data = data or {}

class BaseConnector(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> ConnectorResult:
        """Execute the connector with given context"""
        pass
    
    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return JSON schema for connector configuration"""
        pass