# logger_config.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger():
    logger = logging.getLogger()
    if logger.handlers:
        # Si ya hay handlers configurados, se evita volver a agregarlos.
        return logger

    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Crear un handler para escribir los logs en un archivo
    log_file = os.getenv("LOG_FILE", "app.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)
    file_handler.setFormatter(log_formatter)

    # Crear un handler para mostrar los logs en la consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    # Configurar el logger principal
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
