#!/usr/bin/env bash
# Start-menu launcher for CRMExtender.
# Makes sure the systemd user service is running, waits until the server
# answers, then opens the application in the default browser.
set -uo pipefail

URL="http://127.0.0.1:8000/app/"
SERVICE="crmextender.service"
WAIT_SECONDS=30

systemctl --user start "$SERVICE"

for _ in $(seq 1 $((WAIT_SECONDS * 2))); do
    if curl -fsS -o /dev/null --max-time 2 "$URL"; then
        exec xdg-open "$URL"
    fi
    sleep 0.5
done

MSG="The server did not answer within ${WAIT_SECONDS} seconds. Check: journalctl --user -u crmextender -n 50"
notify-send --app-name=CRMExtender --icon=crmextender "CRMExtender did not start" "$MSG" 2>/dev/null \
    || echo "$MSG" >&2
exit 1
