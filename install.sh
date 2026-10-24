#!/data/data/com.termux/files/usr/bin/env bash
# installer for traficman and tm shortcuts

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/bin"

mkdir -p "$BIN_DIR"
termux-fix-shebang "$DIR/traficman.py" || chmod +x "$DIR/traficman.py"
chmod +x "$DIR/traficman.py"

ln -sf "$DIR/traficman.py" "$BIN_DIR/traficman"
ln -sf "$DIR/traficman.py" "$BIN_DIR/tm"

echo "[INFO] Installed shortcuts in $BIN_DIR:"
echo "       traficman -> $DIR/traficman.py"
echo "       tm        -> $DIR/traficman.py"
echo "[INFO] Test execution:"
"$BIN_DIR/tm" --help | head -n 8
