import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Task T5-4: Traceable execution context adding unique UUID Request IDs 
    to log headers and processing contexts.
    """
    async def dispatch(self, request: Request, call_next):
        # Fetch or generate a unique request identifier
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Expose ID across request state
        request.state.request_id = request_id
        
        # Process Downstream
        response = await call_next(request)
        
        # Append identifier cleanly on final output headers
        response.headers["X-Request-ID"] = request_id
        return response