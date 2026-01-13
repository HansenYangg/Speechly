import logging
import os
from datetime import datetime

def setup_logger(name='speech_evaluator', log_level=logging.INFO):
    """set up logger with file and console handlers"""
    
    # create logs directory if it doesn't exist
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # create file handler
    log_filename = os.path.join(logs_dir, f'speech_evaluator_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in console
    console_handler.setFormatter(console_formatter)
    
    # add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger