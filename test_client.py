#!/usr/bin/env python3
import argparse
import json
import shlex
import sys
from typing import Any

import requests


def build_payload(status: str, ips: list[str], alertname: str, receiver: str) -> dict[str, Any]:
    alerts = [{"labels": {"alertname": alertname, "ip": ip}} for ip in ips]
    return {
        "receiver": receiver,
        "status": status,
        "alerts": alerts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Send test payloads to grafana-hook webhook endpoint.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/webhooks/grafana/ip-blacklist", help="Webhook URL")
    parser.add_argument("--token", required=True, help="Webhook shared secret token")
    parser.add_argument("--token-header", default="X-Webhook-Token", help="Header name for webhook token")
    parser.add_argument("--status", default="firing", help="Grafana alert status (default: firing)")
    parser.add_argument("--alertname", default="SSHGuard IP Flood", help="Alert name label")
    parser.add_argument("--receiver", default="webhook", help="Receiver field in payload")
    parser.add_argument("--ip", dest="ips", action="append", required=True, help="IP to include in payload (repeatable)")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP timeout in seconds")
    parser.add_argument("--debug-curl", action="store_true", help="Print equivalent curl command to stderr")

    args = parser.parse_args()

    payload = build_payload(
        status=args.status,
        ips=args.ips,
        alertname=args.alertname,
        receiver=args.receiver,
    )
    headers = {
        "Content-Type": "application/json",
        args.token_header: args.token,
    }

    if args.debug_curl:
        curl_cmd = (
            f"curl -X POST {shlex.quote(args.url)} "
            f"-H {shlex.quote('Content-Type: application/json')} "
            f"-H {shlex.quote(f'{args.token_header}: {args.token}')} "
            f"--data-raw {shlex.quote(json.dumps(payload))}"
        )
        print(f"DEBUG curl command: {curl_cmd}", file=sys.stderr)

    try:
        response = requests.post(args.url, headers=headers, json=payload, timeout=args.timeout)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)

    return 0 if response.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
