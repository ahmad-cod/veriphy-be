from fastapi import Request, status
from asgi_correlation_id import correlation_id # Get current request ID
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()

class VeriphyException(Exception):
    """Base exception for all custom Veri-phy errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    
class AuthenticationError(VeriphyException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)

class NotFoundError(VeriphyException):
    def __init__(self, resource: str):
        super().__init__(f"{resource} not found", status_code=status.HTTP_404_NOT_FOUND)

async def veriphy_exception_handler(request: Request, exc: VeriphyException):
    """Handles custom domain exceptions safely."""
    logger.warning("Domain exception", path=request.url.path, error=exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "request_id": correlation_id.get()
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions to prevent leaking stack traces/PII."""
    logger.error("Unhandled exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "An internal server error occurred.",
            "request_id": correlation_id.get()
        },
    )