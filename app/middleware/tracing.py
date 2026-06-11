import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate or intercept incoming tracking identifiers
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Make the request ID available on the state for logger context
        request.state.request_id = request_id
        
        # Execute downstream endpoints
        response = await call_next(request)
        
        # Inject trace marker into client headers response payload
        response.headers["X-Request-ID"] = request_id
        return response