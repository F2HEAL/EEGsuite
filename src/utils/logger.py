import logging
import sys
from pathlib import Path
from datetime import datetime
from .paths import LOG_DIR

def setup_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Sets up a logger with both console and file handlers.

    Args:
        name: Name of the logger (None for root logger).
        level: Logging level.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger

    # Formatting - Simpler format to match user preference for clean output
    formatter = logging.Formatter(
        "%(message)s"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    log_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}.log"
    file_handler = logging.FileHandler(LOG_DIR / log_filename)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
