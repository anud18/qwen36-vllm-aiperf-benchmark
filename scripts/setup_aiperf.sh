#!/usr/bin/env bash
# Install aiperf into a local venv (host, aarch64).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q aiperf
echo ">>> aiperf installed:"; aiperf --version || true
