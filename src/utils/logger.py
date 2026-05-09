import logging
import sys
import warnings
from pathlib import Path
from datetime import datetime
from .paths import LOG_DIR

# Filter out specific annoying pyprep messages that are redundant or misleading
class PyPrepFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "Overwriting `ransac` value" in msg:
            return False
        return True

def setup_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Sets up a logger with both console and file handlers.
    If name is None, configures the root logger.

    Args:
        name: Name of the logger (None for root logger).
        level: Logging level.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent adding handlers multiple times to the same logger
    if logger.handlers:
        return logger

    # Formatting - matches tfr_contrast format
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    log_name = name if name else "EEGsuite"
    log_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{log_name}.log"
    file_handler = logging.FileHandler(LOG_DIR / log_filename)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Silence external libraries
    import mne
    mne.set_log_level("WARNING")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    
    pyprep_logger = logging.getLogger("pyprep")
    pyprep_logger.setLevel(logging.WARNING)
    if not any(isinstance(f, PyPrepFilter) for f in pyprep_logger.filters):
        pyprep_logger.addFilter(PyPrepFilter())

    # Also silence specific RuntimeWarnings from MNE/PyPREP regarding digitization points
    warnings.filterwarnings("ignore", message=".*head digitization points.*")

    return logger
