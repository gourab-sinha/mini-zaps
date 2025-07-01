import httpx
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

class WebhookConnector(BaseConnector):
    async def execute(self, context: Dict[str, Any]) -> ConnectorResult:
        try:
            url = self.config["url"]
            method = self.config.get("method", "POST").upper()
            headers = self.config.get("headers", {})
            body = self.config.get("body", {})
            
            # Replace placeholders in body with context data
            processed_body = self._process_template(body, context)
            
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=processed_body if method in ["POST", "PUT", "PATCH"] else None
                )
                
                return ConnectorResult(
                    success=response.status_code < 400,
                    message=f"Webhook {method} to {url}: {response.status_code}",
                    data={
                        "status_code": response.status_code,
                        "response_body": response.text[:1000]  # Truncate long responses
                    }
                )
        except Exception as e:
            return ConnectorResult(
                success=False,
                message=f"Webhook failed: {str(e)}"
            )
    
    def _process_template(self, data: Any, context: Dict[str, Any]) -> Any:
        """Simple template processing - replace {{key}} with context values"""
        if isinstance(data, str):
            for key, value in context.items():
                data = data.replace(f"{{{{{key}}}}}", str(value))
            return data
        elif isinstance(data, dict):
            return {k: self._process_template(v, context) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._process_template(item, context) for item in data]
        return data
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "Target URL for the webhook"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "default": "POST"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers to send"
                },
                "body": {
                    "type": "object",
                    "description": "Request body (supports {{variable}} templating)"
                }
            },
            "required": ["url"]
        }