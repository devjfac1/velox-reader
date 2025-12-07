#!/bin/bash
# Auto-activate venv and run the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/epub_rsvp_reader.py" "$@"


