import asyncio
import sys
import os
from typing import Dict, Any

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from .base import BaseConnector, ConnectorResult
except ImportError:
    # Fallback for direct execution
    from app.connectors.base import BaseConnector, ConnectorResult

class DelayConnector(BaseConnector):
    async def execute(self, context: Dict[str, Any]) -> ConnectorResult:
        try:
            delay_seconds = self.config.get("seconds", 1)
            
            await asyncio.sleep(delay_seconds)
            
            return ConnectorResult(
                success=True,
                message=f"Delayed for {delay_seconds} seconds",
                data={"delay_seconds": delay_seconds}
            )
        except Exception as e:
            return ConnectorResult(
                success=False,
                message=f"Delay failed: {str(e)}"
            )
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Number of seconds to delay",
                    "minimum": 0
                }
            },
            "required": ["seconds"]
        }