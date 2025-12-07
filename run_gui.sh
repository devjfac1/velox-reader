#!/bin/bash
# Launch EPUB reader GUI safely

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Make sure DISPLAY is set
export DISPLAY=:0
xhost +SI:localuser:natyfer

# Activate venv and run the script
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/epub_rsvp_reader.py" "$@"
