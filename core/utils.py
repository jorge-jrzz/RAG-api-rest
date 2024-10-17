import os
import logging
from typing import List
from colorlog import ColoredFormatter


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    formatter = ColoredFormatter(
        "%(log_color)s%(levelname)s: %(name)s  [%(asctime)s] -- %(message)s",
        datefmt='%d/%m/%Y %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

def list_files_with_subdirectories(directory: str) -> List:
    files = []
    for root_dir, sub_dirs, root_files in os.walk(directory):
        for file_name in root_files:
            full_file_path = os.path.join(root_dir, file_name)
            files.append(full_file_path)
    return files

def delete_files_directory(directory: str) -> None:
    files = list_files_with_subdirectories(directory)
    for file in files: 
        try:
            if os.path.isfile(file):
                os.unlink(file)
        except OSError as e:
            raise e
