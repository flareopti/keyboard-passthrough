#!/usr/bin/env python3
import os
import curses
import evdev
import serial
from struct import pack
from evdev import ecodes
import sys

def list_serial_ports():
    # List common Linux serial port names
    return [f"/dev/{d}" for d in os.listdir("/dev") if d.startswith("ttyUSB") or d.startswith("ttyACM")]

def ncurses_selector(stdscr, prompt, options):
    curses.curs_set(0)
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    selected = 0
    while True:
        stdscr.clear()
        stdscr.addstr(1, 2, prompt, curses.A_BOLD)
        for i, opt in enumerate(options):
            attr = (curses.A_REVERSE if i == selected else curses.A_NORMAL)
            stdscr.addstr(3+i, 4, str(opt), attr)
        stdscr.refresh()
        k = stdscr.getch()
        if k == curses.KEY_UP and selected > 0:
            selected -= 1
        elif k == curses.KEY_DOWN and selected < len(options)-1:
            selected += 1
        elif k in (curses.KEY_ENTER, ord("\n")):
            return selected

def pick_devices_ncurses():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    if not devices:
        raise RuntimeError("No evdev input devices found!")
    device_list = [f"{dev.name} ({dev.path})" for dev in devices]
    serials = list_serial_ports()
    if not serials:
        serials = ["/dev/ttyUSB0 (dummy/no serial found)"]

    def _inner(stdscr):
        idx_kbd = ncurses_selector(stdscr, "Select keyboard input device", device_list)
        idx_ser = ncurses_selector(stdscr, "Select serial device", serials)
        return devices[idx_kbd].path, serials[idx_ser].split()[0]

    return curses.wrapper(_inner)

KEYBOARD_PATH, SERIAL_PATH = pick_devices_ncurses()

orig_map = {
    ecodes.KEY_LEFTCTRL: 128,
    ecodes.KEY_LEFTSHIFT: 129,
    ecodes.KEY_LEFTALT: 130,
    ecodes.KEY_LEFTMETA: 131,
    ecodes.KEY_RIGHTCTRL: 132,
    ecodes.KEY_RIGHTSHIFT: 133,
    ecodes.KEY_RIGHTALT: 134,
    ecodes.KEY_RIGHTMETA: 135,
    ecodes.KEY_UP: 218,
    ecodes.KEY_DOWN: 217,
    ecodes.KEY_LEFT: 216,
    ecodes.KEY_RIGHT: 215,
    ecodes.KEY_BACKSPACE: 178,
    ecodes.KEY_ENTER: 176,
    ecodes.KEY_ESC: 177,
    ecodes.KEY_INSERT: 209,
    ecodes.KEY_DELETE: 212,
    ecodes.KEY_PAGEUP: 211,
    ecodes.KEY_PAGEDOWN: 214,
    ecodes.KEY_HOME: 210,
    ecodes.KEY_END: 213,
    ecodes.KEY_CAPSLOCK: 193,
    ecodes.KEY_F1: 194,
    ecodes.KEY_F2: 195,
    ecodes.KEY_F3: 196,
    ecodes.KEY_F4: 197,
    ecodes.KEY_F5: 198,
    ecodes.KEY_F6: 199,
    ecodes.KEY_F7: 200,
    ecodes.KEY_F8: 201,
    ecodes.KEY_F9: 202,
    ecodes.KEY_F10: 203,
    ecodes.KEY_F11: 204,
    ecodes.KEY_F12: 205,
}
keycode_to_ascii = {}
for i in range(26):
    keycode = getattr(ecodes, f"KEY_{chr(ord('A') + i)}")
    letter = chr(ord('a') + i)
    LETTER = chr(ord('A') + i)
    keycode_to_ascii[keycode] = (letter, LETTER)
for i in range(10):
    keycode = getattr(ecodes, f"KEY_{i}")
    digit = chr(ord('0') + i)
    keycode_to_ascii[keycode] = (digit, ")!@#$%^&*("[i])
keycode_to_ascii.update({
    ecodes.KEY_SPACE: (' ', ' '),
    ecodes.KEY_MINUS: ('-', '_'),
    ecodes.KEY_EQUAL: ('=', '+'),
    ecodes.KEY_LEFTBRACE: ('[', '{'),
    ecodes.KEY_RIGHTBRACE: (']', '}'),
    ecodes.KEY_BACKSLASH: ('\\', '|'),
    ecodes.KEY_SEMICOLON: (';', ':'),
    ecodes.KEY_APOSTROPHE: ("'", '"'),
    ecodes.KEY_GRAVE: ('`', '~'),
    ecodes.KEY_COMMA: (',', '<'),
    ecodes.KEY_DOT: ('.', '>'),
    ecodes.KEY_SLASH: ('/', '?'),
})

pressed_keys = set()
def get_ascii_from_event(code):
    shift = (
        ecodes.KEY_LEFTSHIFT in pressed_keys or
        ecodes.KEY_RIGHTSHIFT in pressed_keys
    )
    if code in keycode_to_ascii:
        unshifted, shifted = keycode_to_ascii[code]
        char = shifted if shift else unshifted
        return ord(char)
    return None

def main():
    ser = serial.Serial(SERIAL_PATH, 9600)
    dev = evdev.InputDevice(KEYBOARD_PATH)
    print(f"Using device: {dev.name} at {dev.path}")
    dev.grab()
    try:
        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY:
                code = event.code
                value = event.value  # 1=down, 0=up, 2=hold
                if value == 1:
                    pressed_keys.add(code)
                elif value == 0:
                    pressed_keys.discard(code)
                # Send to serial
                if value in [0, 1]:
                    ascii_code = get_ascii_from_event(code)
                    if ascii_code is not None:
                        press = 1 if value == 1 else 0
                        print(f"{'Pressed' if press else 'Released'} {code} -> {ascii_code} ({chr(ascii_code)})")
                        ser.write(pack("!BB", press, ascii_code))
                    else:
                        keycode = orig_map.get(code, code)
                        press = 1 if value == 1 else 0
                        print(f"{'Pressed' if press else 'Released'} {code} -> {keycode}")
                        ser.write(pack("!BB", press, keycode))
                # Exit hotkey: Ctrl+Delete
                if ecodes.KEY_DELETE in pressed_keys and (
                    ecodes.KEY_LEFTCTRL in pressed_keys or ecodes.KEY_RIGHTCTRL in pressed_keys
                ):
                    print("Ctrl+Delete pressed — exiting.")
                    break
    finally:
        dev.ungrab()
        ser.close()
        sys.exit(0)

if __name__ == "__main__":
    main()