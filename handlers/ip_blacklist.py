import ipaddress
from typing import Any

import requests

from config import Settings


def _extract_alert_ips(payload: dict[str, Any]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        raise ValueError("'alerts' must be an array")

    deduped: dict[str, str] = {}
    rejected: list[dict[str, Any]] = []

    for idx, alert in enumerate(alerts):
        if not isinstance(alert, dict):
            rejected.append(
                {
                    "index": idx,
                    "status": "rejected",
                    "error": "alert must be an object",
                }
            )
            continue

        labels = alert.get("labels") or {}
        if not isinstance(labels, dict):
            rejected.append(
                {
                    "index": idx,
                    "status": "rejected",
                    "error": "labels must be an object",
                }
            )
            continue

        ip_value = labels.get("ip")
        if not ip_value or not isinstance(ip_value, str):
            rejected.append(
                {
                    "index": idx,
                    "status": "rejected",
                    "error": "labels.ip is required",
                }
            )
            continue

        ip_candidate = ip_value.strip()
        try:
            ipaddress.ip_address(ip_candidate)
        except ValueError:
            rejected.append(
                {
                    "index": idx,
                    "ip": ip_candidate,
                    "status": "rejected",
                    "error": "invalid IP address",
                }
            )
            continue

        if ip_candidate in deduped:
            continue

        alertname = labels.get("alertname")
        if not alertname or not isinstance(alertname, str):
            alertname = "unknown_alert"
        deduped[ip_candidate] = alertname

    return deduped, rejected


def process_ip_blacklist_webhook(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    status = payload.get("status")
    if status != "firing":
        alerts = payload.get("alerts")
        received_alerts = len(alerts) if isinstance(alerts, list) else 0
        return {
            "message": "ignored_status",
            "status": status,
            "received_alerts": received_alerts,
            "valid_ips": 0,
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "rejected": 0,
            "results": [],
        }

    ip_to_alertname, rejected_results = _extract_alert_ips(payload)
    results: list[dict[str, Any]] = list(rejected_results)
    succeeded = 0
    failed = 0

    for ip_value, alertname in ip_to_alertname.items():
        reason = f"{settings.iplist_reason_prefix}:{alertname}"
        request_body = {
            "ip_address": ip_value,
            "timeout_seconds": settings.iplist_timeout_seconds,
            "reason": reason,
        }
        url = f"{settings.iplist_addr}/ip-filters/"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {settings.iplist_api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=request_body,
                timeout=settings.request_timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                succeeded += 1
                results.append(
                    {
                        "ip": ip_value,
                        "status": "success",
                        "downstream_status": response.status_code,
                    }
                )
            else:
                failed += 1
                results.append(
                    {
                        "ip": ip_value,
                        "status": "failed",
                        "downstream_status": response.status_code,
                        "downstream_body": response.text[:500],
                    }
                )
        except requests.RequestException as exc:
            failed += 1
            results.append(
                {
                    "ip": ip_value,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    alerts = payload.get("alerts")
    summary = {
        "received_alerts": len(alerts) if isinstance(alerts, list) else 0,
        "valid_ips": len(ip_to_alertname),
        "attempted": len(ip_to_alertname),
        "succeeded": succeeded,
        "failed": failed,
        "rejected": len(rejected_results),
        "results": results,
    }
    return summary
