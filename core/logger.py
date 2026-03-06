"""
Logging configuration with rotating file handler
"""
import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logger(name: str, log_file: str = "logs/entscore.log", level=logging.INFO):
    """
    Setup logger with rotating file handler.

    Args:
        name: Logger name (typically __name__)
        log_file: Path to log file
        level: Logging level

    Returns:
        Configured logger instance
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Rotating file handler (5MB max, keep 3 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler (WARNING and above only)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
