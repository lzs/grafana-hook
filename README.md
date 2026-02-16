# grafana-hook

Standalone Grafana webhook middleware service. It receives Grafana webhook payloads and forwards IP blacklist requests to `iplistd`.

## Endpoint

- `POST /webhooks/grafana/ip-blacklist`
- Auth header: `X-Webhook-Token` (or `WEBHOOK_TOKEN_HEADER` override)

Expected Grafana payload shape:

```json
{
  "receiver": "webhook",
  "status": "firing",
  "alerts": [
    {
      "labels": {
        "alertname": "SSHGuard IP Flood",
        "ip": "9.9.9.9"
      }
    }
  ]
}
```

## Environment

Copy `.env.example` to `.env` and set values:

- `WEBHOOK_SHARED_SECRET` (required)
- `WEBHOOK_TOKEN_HEADER` (default `X-Webhook-Token`)
- `IPLIST_ADDR` (required)
- `IPLIST_API_KEY` (required, must have `write` permission in `iplistd`)
- `IPLIST_TIMEOUT_SECONDS` (default `86400`)
- `IPLIST_REASON_PREFIX` (default `grafana`)
- `REQUEST_TIMEOUT_SECONDS` (default `5`)
- `DEBUG` (default `false`; set `true` to enable debug logs)

## Run

```bash
cd /home/lzs/work/grafana-hook
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8090
```

## Test with curl

```bash
curl -X POST "http://127.0.0.1:8090/webhooks/grafana/ip-blacklist" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: replace-with-random-secret" \
  -d '{
    "receiver": "webhook",
    "status": "firing",
    "alerts": [
      {"labels": {"alertname": "SSHGuard IP Flood", "ip": "9.9.9.9"}},
      {"labels": {"alertname": "SSHGuard IP Flood", "ip": "9.9.9.9"}},
      {"labels": {"alertname": "Bad data", "ip": "not-an-ip"}}
    ]
  }'
```

## Behavior

- Only `status: firing` is processed.
- Extracts `alerts[].labels.ip`.
- Validates and deduplicates IPs per request.
- Forwards each valid IP to `iplistd` `POST /ip-filters/`.
- Returns per-IP results with aggregate counts.
- Returns `502` only when every attempted downstream call fails.

## Test client

Use the included CLI client to send test payloads:

```bash
cd /home/lzs/work/grafana-hook
python test_client.py \
  --token "replace-with-random-secret" \
  --ip 9.9.9.9 \
  --ip 8.8.8.8
```

Test a non-firing payload (should be ignored by middleware):

```bash
python test_client.py \
  --token "replace-with-random-secret" \
  --status resolved \
  --ip 9.9.9.9
```

## Run as systemd service

Create a user service file at `~/.config/systemd/user/grafana-hook.service`:

```ini
[Unit]
Description=Grafana Hook Middleware
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/lzs/work/grafana-hook
EnvironmentFile=/home/lzs/work/grafana-hook/.env
ExecStart=/home/lzs/work/grafana-hook/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8090
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

Then enable and start it:

```bash
cd /home/lzs/work/grafana-hook
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

systemctl --user daemon-reload
systemctl --user enable grafana-hook.service
systemctl --user start grafana-hook.service
systemctl --user status grafana-hook.service
```

View logs:

```bash
journalctl --user -u grafana-hook.service -f
```

Optional (keep service running after logout):

```bash
sudo loginctl enable-linger "$USER"
```
