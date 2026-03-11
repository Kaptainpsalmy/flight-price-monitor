"""
Logging configuration for the Price Monitor service
"""
import logging
import sys
from datetime import datetime

def setup_logger(name):
    """Setup logger with console and file handlers"""

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create formatters - avoid special characters for Windows
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    # Use simple ASCII arrows for Windows console
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Console handler - use UTF-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # File handler
    log_filename = f'logs/price_monitor_{datetime.now().strftime("%Y%m%d")}.log'
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

# Create logs directory if it doesn't exist
import os
os.makedirs('logs', exist_ok=True)