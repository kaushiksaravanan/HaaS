#!/bin/bash
#
# Quick Install Script for vlgdbzo3 (Python 3.6)
# ==============================================
#
# Run this script on vlgdbzo3 after copying the files
#
# Usage:
#   bash install_server.sh
#

set -e  # Exit on error

echo "============================================================"
echo "Remote Exec Server - Quick Install for Python 3.6"
echo "============================================================"
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '3\.\d+')
echo "Found Python $PYTHON_VERSION"
echo ""

if [[ "$PYTHON_VERSION" == "3.6" ]]; then
    echo "✓ Python 3.6 detected - using compatible dependencies"
    REQUIREMENTS="requirements_python36.txt"
else
    echo "! Python $PYTHON_VERSION detected"
    echo "  (Script optimized for 3.6, but will try to install)"
    REQUIREMENTS="requirements_python36.txt"
fi
echo ""

# Check if files exist
echo "Checking required files..."
if [ ! -f "remote_exec_server.py" ]; then
    echo "✗ remote_exec_server.py not found!"
    echo "  Please copy it to $(pwd) first"
    exit 1
fi
echo "✓ remote_exec_server.py found"

if [ ! -f "$REQUIREMENTS" ]; then
    echo "! $REQUIREMENTS not found"
    echo "  Will install dependencies manually"
    MANUAL_INSTALL=1
else
    echo "✓ $REQUIREMENTS found"
    MANUAL_INSTALL=0
fi
echo ""

# Upgrade pip
echo "Upgrading pip..."
python3 -m pip install --user --upgrade pip
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies..."
if [ $MANUAL_INSTALL -eq 1 ]; then
    echo "Installing manually (no requirements file)..."
    python3 -m pip install --user fastapi==0.68.2 uvicorn==0.15.0 pydantic==1.8.2
else
    python3 -m pip install --user -r $REQUIREMENTS
fi
echo "✓ Dependencies installed"
echo ""

# Verify installation
echo "Verifying installation..."
python3 -c "import fastapi, uvicorn, pydantic; print('✓ All modules imported successfully')"
echo ""

# Show FastAPI version
echo "Installed versions:"
python3 -c "import fastapi, uvicorn, pydantic; print(f'  FastAPI: {fastapi.__version__}'); print(f'  Uvicorn: {uvicorn.__version__}'); print(f'  Pydantic: {pydantic.VERSION}')" 2>/dev/null || python3 -c "import fastapi, uvicorn, pydantic; print('  FastAPI:', fastapi.__version__); print('  Uvicorn:', uvicorn.__version__); print('  Pydantic:', pydantic.VERSION)"
echo ""

echo "============================================================"
echo "✓ Installation complete!"
echo "============================================================"
echo ""
echo "Pre-configured API Key:"
echo "  REMOTE_EXEC_KEY_REVOKED_PLACEHOLDER_0000000000000000"
echo ""
echo "To start the server:"
echo "  python3 remote_exec_server.py"
echo ""
echo "To run in background:"
echo "  nohup python3 remote_exec_server.py > remote_exec_server.log 2>&1 &"
echo ""
echo "To check if running:"
echo "  ps aux | grep remote_exec_server"
echo "  netstat -tulpn | grep 9999"
echo ""
echo "To view logs:"
echo "  tail -f remote_exec_server.log"
echo ""
