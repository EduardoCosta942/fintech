from dotenv import load_dotenv
from pathlib import Path
import os

from fintech.exceptions import EnvNotFoundError

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_ai_config = None


def get_env_variable(name, default=None) -> str:
    value = os.getenv(name)

    if value is None:
        raise EnvNotFoundError(
            f"Environment variable '{name}' is not set and no default value provided."
        )

    return value


def get_env_int(name, default=None) -> int:
    value = os.getenv(name, default)

    if value is None:
        raise EnvNotFoundError(
            f"Environment variable '{name}' is not set and no default value provided."
        )

    return int(value)


def get_ai_config():
    global _ai_config

    if _ai_config is None:
        def load_config():
            return {
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", None),
                "GROQ_API_KEY": os.getenv("GROQ_API_KEY", None),
                "GEMINI_MODEL": os.getenv("GEMINI_MODEL", None),
                "GROQ_MODEL": os.getenv("GROQ_MODEL", None)
            }

        config = load_config()

        if not config:
            _ai_config = None
        else:
            _ai_config = list(config.values())

    return _ai_config