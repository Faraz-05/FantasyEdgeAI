import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=_BACKEND_ENV)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def demo_mode_enabled() -> bool:
    return env_flag("DEMO_MODE")
