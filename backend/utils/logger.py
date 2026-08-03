import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from config import settings

def setup_logger(name: str = "gov_doc_system") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    if logger.handlers:
        return logger
        
    log_format = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
    )
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    # File Handler
    log_file = os.path.join(settings.LOG_DIR, "system.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()
