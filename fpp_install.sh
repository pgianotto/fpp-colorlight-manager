#!/bin/bash
# Install hook for the Colorlight Manager FPP plugin.
# Called by FPP's plugin manager after the repo is cloned into
# /home/fpp/media/plugins/fpp-colorlight-manager (or /media/plugins on some setups).

PLUGINDIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DISCOVER_SCRIPT="${PLUGINDIR}/backend/receiver_discovery.py"
SUDOERS_FILE="/etc/sudoers.d/fpp-colorlight-manager"

chmod +x "${DISCOVER_SCRIPT}"

# Raw-socket discovery needs CAP_NET_RAW (and CAP_NET_ADMIN to toggle
# promiscuous mode on the receive socket, matching what FPP's own
# ColorLight-5a-75 channel output already does). Rather than granting that
# broadly (e.g. setcap on the python3 interpreter itself, which would hand
# the capability to every script anyone runs with that interpreter), scope
# a sudoers rule to this one script path so the web UI (running as the fpp
# user) can invoke only this discovery tool with no password prompt.
cat > "${SUDOERS_FILE}" <<EOF
fpp ALL=(root) NOPASSWD: /usr/bin/env python3 ${DISCOVER_SCRIPT}*
EOF
chmod 440 "${SUDOERS_FILE}"

if visudo -c -f "${SUDOERS_FILE}" > /dev/null 2>&1; then
    echo "Colorlight Manager: sudoers rule installed for ${DISCOVER_SCRIPT}"
else
    echo "Colorlight Manager: WARNING - sudoers rule failed validation, removing it." >&2
    rm -f "${SUDOERS_FILE}"
fi

exit 0
