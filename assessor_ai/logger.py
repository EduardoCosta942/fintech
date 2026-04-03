import logging
import sys
from typing import Optional

from assessor_ai.enum import Environment
from assessor_ai.env_loader import get_env_variable
from assessor_ai.exceptions import EnvNotFoundError


class _ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[94m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[95m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


class _LoggerManager:
    _instance: Optional[logging.Logger] = None

    @classmethod
    def _setup(cls) -> logging.Logger:
        logger = logging.getLogger("fintech")

        if logger.handlers:
            return logger

        try:
            if (get_env_variable("ENV").lower() == Environment.DEVELOPMENT.name.lower()):
                logger.setLevel(logging.DEBUG)
            else:
                logger.setLevel(logging.INFO)
        except EnvNotFoundError:
            logger.setLevel(logging.INFO)
            logger.warning("ENV variable not found, defaulting to INFO level")
            
        formatter = _ColoredFormatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

        return logger

    @classmethod
    def get_logger(cls) -> logging.Logger:
        if cls._instance is None:
            cls._instance = cls._setup()
        return cls._instance


# Interface pública (controlada)
def log_info(message: str):
    _LoggerManager.get_logger().info(message)


def log_warning(message: str):
    _LoggerManager.get_logger().warning(message)


def log_error(message: str):
    _LoggerManager.get_logger().error(message)


def log_debug(message: str):
    _LoggerManager.get_logger().debug(message)