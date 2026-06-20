"""Configuration, loaded from environment / .env (never hard-coded in source)."""
from __future__ import annotations

import os
from dataclasses import dataclass

try:  # dotenv is optional; plain environment variables still work without it
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    base_url: str = os.getenv("WCB_BASE_URL", "http://localhost:8000/v1")
    api_key: str = os.getenv("WCB_API_KEY", "EMPTY")
    model: str = os.getenv("WCB_MODEL", "Qwen/Qwen3-14B-AWQ")
    grid: int = int(os.getenv("WCB_GRID", "8"))
    agents: int = int(os.getenv("WCB_AGENTS", "4"))
    npcs: int = int(os.getenv("WCB_NPCS", "4"))
    tick_ms: int = int(os.getenv("WCB_TICK_MS", "500"))


def load_config() -> Config:
    return Config()
