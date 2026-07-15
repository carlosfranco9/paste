#!/usr/bin/env bash
set -euo pipefail

APP_NAME="paste"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST_DIR="${DESTDIR:-/usr/local}"

echo "Installing Paste — Clipboard Manager"

# --- check Python ---
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found" >&2
    exit 1
fi

# --- install system dependencies ---
echo "Installing system dependencies..."
if command -v apt-get &>/dev/null; then
    sudo apt-get install -y python3-pip python3-pyside2.qtwidgets xclip 2>/dev/null || true
elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm python-pip python-pyside2 xclip 2>/dev/null || true
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3-pip python3-pyside2 xclip 2>/dev/null || true
fi

# --- install Python deps ---
echo "Installing Python dependencies..."
pip3 install --user --upgrade PySide2 python-xlib pyperclip psutil Pillow 2>/dev/null || true
pip3 install --user --upgrade PySide2 2>/dev/null || true

# --- copy application ---
echo "Copying application to $DEST_DIR/lib/$APP_NAME/"
sudo mkdir -p "$DEST_DIR/lib/$APP_NAME"
sudo cp -r "$SRC_DIR/src" "$DEST_DIR/lib/$APP_NAME/src"
sudo cp "$SRC_DIR/pyproject.toml" "$DEST_DIR/lib/$APP_NAME/"
find "$DEST_DIR/lib/$APP_NAME" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

# --- install launcher script ---
echo "Creating launcher..."
sudo tee "$DEST_DIR/bin/$APP_NAME" > /dev/null <<LAUNCHER
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$DEST_DIR/lib/$APP_NAME"
if [[ ! -d "\$APP_DIR/src" ]]; then
    echo "Paste installation is incomplete: \$APP_DIR/src not found" >&2
    exit 1
fi

export PYTHONPATH="\$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
cd "\$APP_DIR"
exec python3 -m src.main "\$@"
LAUNCHER
sudo chmod +x "$DEST_DIR/bin/$APP_NAME"

# --- install desktop entry ---
echo "Installing desktop entry..."
mkdir -p "$HOME/.local/share/applications"
cp "$SRC_DIR/packaging/paste.desktop" "$HOME/.local/share/applications/$APP_NAME.desktop"
sed -i "s|Exec=paste|Exec=$DEST_DIR/bin/$APP_NAME|g" "$HOME/.local/share/applications/$APP_NAME.desktop"

# --- install icon ---
echo "Installing icon..."
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
cp "$SRC_DIR/packaging/paste.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_NAME.svg"

# --- autostart ---
echo "Setting up autostart..."
mkdir -p "$HOME/.config/autostart"
cp "$HOME/.local/share/applications/$APP_NAME.desktop" "$HOME/.config/autostart/"

echo ""
echo "✓ Paste installed successfully!"
echo "  - Launch: paste"
echo "  - Hotkey: Ctrl+Shift+V"
echo "  - Autostart enabled (login will auto-launch)"
echo ""
echo "You may need to log out and back in for the tray icon to appear."
