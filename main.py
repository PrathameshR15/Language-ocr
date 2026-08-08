import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from config import settings
from backend.api.routes import router as api_router
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.middleware.error_handler import global_exception_handler
from backend.utils.logger import logger

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade AI-powered Multilingual Document Translation & Intelligence System supporting Indian and global languages, OCR, LLM enhancement, side-by-side comparison, and multi-format document generation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middleware & Exception Handling
app.add_middleware(RateLimitMiddleware)
app.add_exception_handler(Exception, global_exception_handler)

# Include API Router
app.include_router(api_router)

# Mount frontend directory for static serving
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
async def root():
    """Serve web dashboard main page."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    host_display = "localhost" if settings.HOST in ("0.0.0.0", "127.0.0.1") else settings.HOST
    logger.info(f"Starting {settings.APP_NAME} on http://{host_display}:{settings.PORT}")
    
    # Restrict reload watching to source directories only so file uploads/generated outputs don't trigger server restarts
    reload_dirs = [
        os.path.join(os.path.dirname(__file__), "backend"),
        os.path.join(os.path.dirname(__file__), "frontend")
    ] if settings.DEBUG else None

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        reload_dirs=reload_dirs
    )

# Live server reloaded with enhanced CMAP font artifact classifier.

