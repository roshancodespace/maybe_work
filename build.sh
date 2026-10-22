#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=========================================================="
echo " Building Standalone Linux Executable"
echo "=========================================================="

PYTHON_BIN="$DIR/.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    echo "Creating virtual environment..."
    uv venv "$DIR/.venv"
    uv pip install --python "$PYTHON_BIN" fastapi uvicorn websockets pydantic pillow pyinstaller
else
    "$DIR/.venv/bin/pip" install pyinstaller 2>/dev/null || uv pip install --python "$PYTHON_BIN" pyinstaller
fi

echo "Running PyInstaller..."
"$DIR/.venv/bin/pyinstaller" --clean -y android_automator.spec

if [ -f "$DIR/dist/android-automator-linux" ]; then
    chmod +x "$DIR/dist/android-automator-linux"
    SIZE=$(du -h "$DIR/dist/android-automator-linux" | cut -f1)
    echo "=========================================================="
    echo " Build SUCCESSFUL!"
    echo " Executable: $DIR/dist/android-automator-linux ($SIZE)"
    echo " To run:"
    echo "   ./dist/android-automator-linux --port 28491"
    echo "=========================================================="
else
    echo "Build failed: binary not found in dist/"
    exit 1
fi
