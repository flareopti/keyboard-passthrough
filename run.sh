#!/bin/bash
[[ $(/usr/bin/id -u) -ne 0 ]] && echo "Not running as root" && exit
if [[ ! -d venv ]]; then
    python -m venv venv
    source venv/bin/activate
    python -m pip install pyserial evdev
fi
source venv/bin/activate
python pass.py
