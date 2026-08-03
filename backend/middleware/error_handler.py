from fastapi import Request
from fastapi.responses import JSONResponse
from backend.utils.logger import logger
from backend.utils.file_validator import FileValidationError

async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, FileValidationError):
        logger.warning(f"File validation error at {request.url.path}: {exc}")
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "error_type": "FileValidationError"}
        )
        
    logger.error(f"Unhandled server error at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred during document processing.", "error_type": type(exc).__name__}
    )
