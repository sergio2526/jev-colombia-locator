import os

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Falta configurar la variable de entorno {name} (ver .env.example)")
    return value


class Config:
    JEV_API_URL = os.environ.get("JEV_API_URL", "https://api.typesafe.ai/v1/systemone")
    JEV_MODEL = os.environ.get("JEV_MODEL", "jev-latest")
    API_COLOMBIA_BASE_URL = os.environ.get(
        "API_COLOMBIA_BASE_URL", "https://api-colombia.com/api/v1"
    )
    FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or "dev-secret-key-change-me"
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    # Default distinto de 5000: en macOS ese puerto suele estar ocupado por
    # el AirPlay Receiver (ControlCenter) del sistema.
    FLASK_PORT = int(os.environ.get("FLASK_PORT", "5050"))

    @property
    def JEV_API_KEY(self) -> str:
        return _require("JEV_API_KEY")


config = Config()
