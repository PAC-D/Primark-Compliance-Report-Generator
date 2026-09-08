import logging
import sys
from pathlib import Path
from datetime import datetime

LOG_FILE = Path(__file__).parent / "logs" / "run.log"

def setup_logging():
    """Configure logging to file and console."""
    LOG_FILE.parent.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def get_logger(name=None):
    """Get a logger instance."""
    return logging.getLogger(name)