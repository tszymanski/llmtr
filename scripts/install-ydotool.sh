#!/usr/bin/env bash
# Install ydotool 1.0.4 (client + ydotoold daemon) for llmtr on GNOME Wayland.
#
# - replaces Ubuntu's old ydotool 0.1.8 package (different CLI, no daemon)
# - gives the logged-in desktop user access to /dev/uinput (udev "uaccess" ACL, no group change,
#   no re-login)
# - runs ydotoold as a systemd *user* service with its socket at $XDG_RUNTIME_DIR/.ydotool_socket,
#   which is where llmtr looks for it
#
# Run as your normal user (not root); it calls sudo where needed. Safe to re-run.
set -euo pipefail

VERSION="v1.0.4"
BASE="https://github.com/ReimuNotMoe/ydotool/releases/download/${VERSION}"
# sha256 of the upstream release assets, recorded 2026-10-04
SHA_YDOTOOL="daa83507a596d6839b7467540382dbdc6e4bf64ebfa4f7d6416e877d9a522c0c"
SHA_YDOTOOLD="3f14f96308935214c0fb154507360f7632e7deda1935dc2d538259fd9986ed36"
UDEV_RULE="/etc/udev/rules.d/60-ydotool-uinput.rules"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

if [[ $EUID -eq 0 ]]; then
    echo "Run this as your normal user, not root (it uses sudo itself)." >&2
    exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "==> Downloading ydotool ${VERSION}"
curl -fsSLo "$tmp/ydotool" "$BASE/ydotool-release-ubuntu-latest"
curl -fsSLo "$tmp/ydotoold" "$BASE/ydotoold-release-ubuntu-latest"
echo "$SHA_YDOTOOL  $tmp/ydotool" | sha256sum -c --quiet
echo "$SHA_YDOTOOLD  $tmp/ydotoold" | sha256sum -c --quiet

if dpkg -s ydotool >/dev/null 2>&1; then
    echo "==> Removing Ubuntu ydotool package (0.1.x)"
    sudo apt-get remove -y ydotool
fi

echo "==> Installing binaries to /usr/local/bin"
sudo install -m 0755 "$tmp/ydotool" /usr/local/bin/ydotool
sudo install -m 0755 "$tmp/ydotoold" /usr/local/bin/ydotoold

echo "==> Granting the desktop user access to /dev/uinput (${UDEV_RULE})"
echo 'KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", OPTIONS+="static_node=uinput"' \
    | sudo tee "$UDEV_RULE" >/dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change /dev/uinput

echo "==> Installing user service ydotoold.service"
mkdir -p "$UNIT_DIR"
cat >"$UNIT_DIR/ydotoold.service" <<'EOF'
[Unit]
Description=ydotool daemon (virtual input for llmtr)

[Service]
ExecStart=/usr/local/bin/ydotoold --socket-path=%t/.ydotool_socket --socket-perm=0600
# ydotoold leaves its socket file behind when it stops; remove it so llmtr sees it is gone
ExecStopPost=/bin/rm -f %t/.ydotool_socket
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now ydotoold.service
systemctl --user restart ydotoold.service

echo "==> Checking"
sleep 1
getfacl -p /dev/uinput 2>/dev/null | grep "^user:$USER" || ls -l /dev/uinput
systemctl --user --no-pager --lines=0 status ydotoold.service | head -3
socket="${XDG_RUNTIME_DIR}/.ydotool_socket"
[[ -S "$socket" ]] && echo "socket: $socket" || { echo "socket missing: $socket" >&2; exit 1; }
# press and release Shift: harmless, proves the daemon can inject keys
YDOTOOL_SOCKET="$socket" /usr/local/bin/ydotool key 42:1 42:0
echo "OK: ydotool ${VERSION} ready for llmtr"
