#!/bin/bash
# Called by start-macos.sh with the app URL. If the launchd agent runs
# Odysseus, open it and succeed, so the script doesn't start a second server
# that would fail on the busy port. Otherwise fail and let the script go on.
command -v launchctl >/dev/null 2>&1 || exit 1
launchctl print "gui/$(id -u)/local.odysseus" >/dev/null 2>&1 || exit 1
echo "▶ Odysseus runs as a background service (launchd: local.odysseus) - opening $1"
echo "  Restart: launchctl kickstart -k gui/$(id -u)/local.odysseus"
echo "  Logs:    logs/app-service.log    Remove the service: bash launchd/uninstall.sh"
[ -z "${ODYSSEUS_NO_OPEN:-}" ] && open "$1"
exit 0
