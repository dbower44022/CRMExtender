#!/usr/bin/env bash
# Install, remove, restart or inspect the CRMExtender desktop deployment on
# a Linux desktop (systemd user service + start-menu entry).
#
#   deploy/desktop/install-desktop.sh install     # or no argument
#   deploy/desktop/install-desktop.sh restart     # after pulling new code
#   deploy/desktop/install-desktop.sh status
#   deploy/desktop/install-desktop.sh logs
#   deploy/desktop/install-desktop.sh uninstall
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SERVICE="crmextender.service"

BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
UNIT_DIR="$HOME/.config/systemd/user"

LAUNCHER="$BIN_DIR/crmextender-launch"
DESKTOP="$APPS_DIR/crmextender.desktop"
ICON="$ICON_DIR/crmextender.svg"
UNIT="$UNIT_DIR/$SERVICE"

refresh_desktop_caches() {
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
    gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
}

do_install() {
    [ -x "$REPO/.venv/bin/python" ] || {
        echo "No virtual environment at $REPO/.venv — create it first." >&2; exit 1; }
    [ -f "$REPO/.env" ] || echo "Warning: $REPO/.env not found; the server will use default settings." >&2

    mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR" "$UNIT_DIR"
    install -m 755 "$HERE/crmextender-launch.sh" "$LAUNCHER"
    install -m 644 "$HERE/crmextender.svg" "$ICON"
    sed "s|@LAUNCHER@|$LAUNCHER|g" "$HERE/crmextender.desktop" > "$DESKTOP"
    sed "s|@REPO@|$REPO|g" "$HERE/crmextender.service" > "$UNIT"

    systemctl --user daemon-reload
    systemctl --user enable --now "$SERVICE"
    refresh_desktop_caches

    echo "Installed:"
    echo "  service   $UNIT  (enabled, started)"
    echo "  launcher  $LAUNCHER"
    echo "  menu      $DESKTOP"
    echo "  icon      $ICON"
    echo "CRMExtender now appears in the Office menu. Restart after a code change with:"
    echo "  $HERE/install-desktop.sh restart"
}

do_uninstall() {
    systemctl --user disable --now "$SERVICE" 2>/dev/null || true
    rm -f "$UNIT" "$LAUNCHER" "$DESKTOP" "$ICON"
    systemctl --user daemon-reload
    refresh_desktop_caches
    echo "Removed the CRMExtender service, launcher, menu entry and icon."
}

case "${1:-install}" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    restart)   systemctl --user restart "$SERVICE"; systemctl --user --no-pager status "$SERVICE" | head -5 ;;
    status)    systemctl --user --no-pager status "$SERVICE" ;;
    logs)      journalctl --user -u "$SERVICE" -n 50 --no-pager ;;
    *) echo "Usage: $0 [install|uninstall|restart|status|logs]" >&2; exit 2 ;;
esac
