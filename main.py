from typing import Any
import hmac
import json
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from config import Settings, load_settings
from handlers.ip_blacklist import process_ip_blacklist_webhook

settings: Settings = load_settings()
logger = logging.getLogger("grafana_hook")
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

app = FastAPI(
    title="Grafana Hook Middleware",
    description="Webhook middleware for Grafana integrations",
    version="1.0.0",
)


def _verify_webhook_token(request: Request) -> None:
    provided = request.headers.get(settings.webhook_token_header)
    if not provided:
        raise HTTPException(status_code=401, detail="Missing webhook token")
    if not hmac.compare_digest(provided, settings.webhook_shared_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook token")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/grafana/ip-blacklist")
async def grafana_ip_blacklist(request: Request) -> JSONResponse:
    _verify_webhook_token(request)

    try:
        payload: Any = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    if "status" not in payload:
        raise HTTPException(status_code=400, detail="Payload missing 'status'")
    if "alerts" not in payload:
        raise HTTPException(status_code=400, detail="Payload missing 'alerts'")

    logger.debug("Received webhook payload JSON: %s", json.dumps(payload, sort_keys=True))

    try:
        summary = process_ip_blacklist_webhook(payload, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "Processed webhook: received_alerts=%s attempted=%s succeeded=%s failed=%s rejected=%s",
        summary.get("received_alerts"),
        summary.get("attempted"),
        summary.get("succeeded"),
        summary.get("failed"),
        summary.get("rejected"),
    )

    attempted = int(summary.get("attempted", 0))
    succeeded = int(summary.get("succeeded", 0))
    failed = int(summary.get("failed", 0))
    if attempted > 0 and succeeded == 0 and failed > 0:
        return JSONResponse(status_code=502, content=summary)

    return JSONResponse(status_code=200, content=summary)
