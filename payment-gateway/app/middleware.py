import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.structured_logger import client_ip_var, session_id_var


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session_id = request.headers.get("X-Session-ID") or str(uuid.uuid4())
        client_ip = request.client.host if request.client else ""
        session_id_var.set(session_id)
        client_ip_var.set(client_ip)
        response = await call_next(request)
        response.headers["X-Session-ID"] = session_id
        return response
