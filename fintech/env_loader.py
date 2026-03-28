try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False
import os

load_dotenv()

_ai_config = None

def get_env_variable(name, default=None) -> str:
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"Environment variable '{name}' is not set and no default value provided.")
    return value

def get_env_int(name, default=None) -> int:
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Environment variable '{name}' is not set and no default value provided.")
    return int(value)

def get_ai_config():
    global _ai_config
    if _ai_config is None:
        def load_config():
            return {
                "GEMINI_API_KEY": get_env_variable("GEMINI_API_KEY"),
                "GROQ_API_KEY": get_env_variable("GROQ_API_KEY"),
                "GEMINI_MODEL": get_env_variable("GEMINI_MODEL"),
                "GROQ_MODEL": get_env_variable("GROQ_MODEL")
            }
        
        _ai_config = load_config().values()
    return _ai_config

