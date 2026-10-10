#!/usr/bin/env bash
# Remove the Odysseus launchd agents and stop their servers. Nothing in the
# repo or data/ is touched; ./start-macos.sh works as before afterwards.
set -uo pipefail
DOMAIN="gui/$(id -u)"
for a in local.odysseus local.odysseus.apfel local.odysseus.chroma; do
    if launchctl bootout "$DOMAIN/$a" 2>/dev/null; then echo "✓ stopped $a"; fi
    rm -f "$HOME/Library/LaunchAgents/$a.plist"
done
echo "✓ agents removed. Start manually with: cd /Users/cedrik/odysseus && ./start-macos.sh"
