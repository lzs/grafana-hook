import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    webhook_shared_secret: str
    webhook_token_header: str
    iplist_addr: str
    iplist_api_key: str
    iplist_timeout_seconds: int
    iplist_reason_prefix: str
    request_timeout_seconds: int
    debug: bool


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "f", "no", "n", "off", ""}:
        return False
    raise RuntimeError(f"{name} must be a boolean value (true/false)")


def load_settings() -> Settings:
    webhook_shared_secret = _require_env("WEBHOOK_SHARED_SECRET")
    iplist_addr = _require_env("IPLIST_ADDR").rstrip("/")
    iplist_api_key = _require_env("IPLIST_API_KEY")

    webhook_token_header = os.getenv("WEBHOOK_TOKEN_HEADER", "X-Webhook-Token").strip() or "X-Webhook-Token"
    iplist_timeout_seconds = int(os.getenv("IPLIST_TIMEOUT_SECONDS", "86400"))
    iplist_reason_prefix = os.getenv("IPLIST_REASON_PREFIX", "grafana").strip() or "grafana"
    request_timeout_seconds = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))
    debug = _env_bool("DEBUG", default=False)

    if iplist_timeout_seconds <= 0:
        raise RuntimeError("IPLIST_TIMEOUT_SECONDS must be greater than 0")
    if request_timeout_seconds <= 0:
        raise RuntimeError("REQUEST_TIMEOUT_SECONDS must be greater than 0")

    return Settings(
        webhook_shared_secret=webhook_shared_secret,
        webhook_token_header=webhook_token_header,
        iplist_addr=iplist_addr,
        iplist_api_key=iplist_api_key,
        iplist_timeout_seconds=iplist_timeout_seconds,
        iplist_reason_prefix=iplist_reason_prefix,
        request_timeout_seconds=request_timeout_seconds,
        debug=debug,
    )
