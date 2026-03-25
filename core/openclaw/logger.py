import logging
import os
from pathlib import Path

class OpenClawLogger:
    """Logger estructurado con niveles y destinos configurables"""

    def __init__(self, name: str = "OpenClaw", log_file: str = "openclaw.log"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Evitar handlers duplicados
        if not self.logger.handlers:
            # Formato para archivo
            file_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # Formato para consola (más limpio)
            console_formatter = logging.Formatter(
                '%(message)s'
            )

            # Handler de archivo
            try:
                fh = logging.FileHandler(log_file, encoding='utf-8')
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(file_formatter)
                self.logger.addHandler(fh)
            except (PermissionError, OSError):
                pass  # Si no puede escribir archivo, solo consola

            # Handler de consola (solo warnings+)
            ch = logging.StreamHandler()
            ch.setLevel(logging.WARNING)
            ch.setFormatter(console_formatter)
            self.logger.addHandler(ch)

    def debug(self, msg: str, **kwargs):
        self.logger.debug(msg)

    def info(self, msg: str, **kwargs):
        self.logger.info(msg)

    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg)

    def error(self, msg: str, exc_info: bool = False, **kwargs):
        self.logger.error(msg, exc_info=exc_info)

    def critical(self, msg: str, **kwargs):
        self.logger.critical(msg)

logger = OpenClawLogger()
