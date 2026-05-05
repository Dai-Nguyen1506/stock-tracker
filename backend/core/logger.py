import logging
import sys

# Cấu hình logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

def setup_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Console Handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    if not logger.handlers:
        logger.addHandler(handler)
        
    return logger

# Tạo một logger mặc định cho toàn app
logger = setup_logger("stock-tracker")
