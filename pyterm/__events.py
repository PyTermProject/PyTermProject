import time
import select
import blessed
import string
import threading
import sys
import termios
import tty
if sys.platform == "darwin":
    from AppKit import NSWorkspace
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID
    )
elif sys.platform == "win32":
    import win32gui
from pynput import keyboard

CLOSED = False

symb = {
    "\t": "tab",
    "\n": "return",
    "\r": "backspace",
    " ": "space",
    "`": "backtick",
    "~": "tilde",
    "!": "exclamation",
    "@": "at sign",
    "#": "hashtag",
    "$": "dollar sign",
    "%": "percent sign",
    "^": "exponent",
    "&": "and",
    "*": "asterisk",
    "(": "open round bracket",
    ")": "close round bracket",
    "-": "minus",
    "_": "underscore",
    "=": "equals",
    "+": "plus",
    "[": "open square bracket",
    "]": "close square bracket",
    "{": "open brace",
    "}": "close brace",
    "\\": "backslash",
    "/": "slash",
    "|": "vertical pipe",
    ";": "semicolon",
    ":": "colon",
    "'": "single quote",
    '"': "double quotes",
    ",": "comma",
    ".": "dot",
    "<": "left angle bracket",
    ">": "right angle bracket",
    "?": "question mark"
}


def get_key_name(key):
    try:
        n = key.name.upper()
    except AttributeError:
        try:
            n = key.char
        except AttributeError:
            n = key
    if n in list(symb.keys()):
        n = symb[n].replace(" ", "_").upper()
    name = "KEY_" + n
    return name


def get_win():
    if sys.platform == "darwin":
        curr_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        curr_pid = NSWorkspace.sharedWorkspace().activeApplication()['NSApplicationProcessIdentifier']
        curr_app_name = curr_app.localizedName()
        options = kCGWindowListOptionOnScreenOnly
        windowList = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        for window in windowList:
            pid = window['kCGWindowOwnerPID']
            windowNumber = window['kCGWindowNumber']
            ownerName = window['kCGWindowOwnerName']
            geometry = window['kCGWindowBounds']
            windowTitle = window.get('kCGWindowName', u'Unknown')
            if curr_pid == pid:
                # print("%s - %s (PID: %d, WID: %d): %s" % (
                # ownerName, windowTitle.encode('ascii', 'ignore'), pid, windowNumber, geometry))
                return "|".join((str(ownerName), str(pid)))  # , str(windowTitle.encode('ascii', 'ignore'))
    elif sys.platform == 'win32':
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())

pressed = {
    get_key_name(i): False
    for i in [
        *list(keyboard.Key.__dict__["_member_map_"].values()),
        *list(string.printable.lower().replace("\x0b", "").replace("\x0c", ""))
    ]
}

events = []

start_term = get_win()


def enable_mouse_tracking():
    sys.stdout.write("\033[?1003h")
    sys.stdout.flush()


def disable_mouse_tracking():
    sys.stdout.write("\033[?1003l")
    sys.stdout.flush()


def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
    if start_term != get_win():
        for k in pressed.keys():
            pressed[k] = False
        return
    try:
        name = "KEY_" + key.name.upper()
    except AttributeError:
        name = "KEY_" + key.char
    if name not in pressed:
        pressed[name] = False
    if {"values": (name, "KEYDOWN"), "type": "KEY"} not in events:
        events.append({"values": (name, "KEYDOWN"), "type": "KEY"})

    if not pressed[name]:
        pressed[name] = True


def on_release(key: keyboard.Key | keyboard.KeyCode | None) -> None:
    if start_term != get_win():
        for k in pressed.keys():
            pressed[k] = False
        return
    try:
        name = "KEY_" + key.name.upper()
    except AttributeError:
        name = "KEY_" + key.char
    if name not in pressed:
        pressed[name] = False

    if {"values": (name, "KEYUP"), "type": "KEY"} not in events:
        events.append({"values": (name, "KEYUP"), "type": "KEY"})

    if pressed[name]:
        pressed[name] = False

def close():
    global CLOSED
    CLOSED = True


def to_name(button):
    match button:
        case 0:
            return "LeftMouseDown"
        case 3:
            return "LeftMouseUp"
        case 35:
            return "MouseMove"
        case 64:
            return "ScrollDown"
        case 65:
            return "ScrollUp"
        case 67:
            return "ScrollRight"
        case 66:
            return "ScrollLeft"
        case 32:
            return "MouseMove"


def start(closed):
    try:
        # with keyboard.Listener(
        #         on_press=on_press,
        #         on_release=on_release) as listener:
        term = blessed.Terminal()
        with term.cbreak(), term.hidden_cursor():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            enable_mouse_tracking()
            tty.setcbreak(fd)
            # tty.setraw(fd)
            while not closed():
                # time.sleep(0.01)
                if select.select([sys.stdin, ], [], [], .1)[0]:
                    data = sys.stdin.buffer.read(1)
                    if data == b"\033":
                        seq = sys.stdin.buffer.read(2)
                        if seq == b"[M":
                            # event = data[3:]
                            # if len(event) >= 3:
                            event = sys.stdin.buffer.read(3)
                            button = event[0] - 32
                            col = event[2] - 32 - 1
                            row = event[1] - 32 - 1
                            if {"values": (to_name(button), (row, col*2)), "type": "MOUSE"} not in events:
                                events.append({"values": (to_name(button), (row, col*2)), "type": "MOUSE"})
                        else:
                            decoded = None
                            if seq == b"[A":
                                decoded = "KEY_UP"
                            elif seq == b"[B":
                                decoded = "KEY_DOWN"
                            elif seq == b"[C":
                                decoded = "KEY_RIGHT"
                            elif seq == b"[D":
                                decoded = "KEY_LEFT"
                            elif seq == b"x7f":
                                decoded = "KEY_BACKSPACE"
                            if decoded:
                                events.append({"values": (decoded, "KEYDOWN"), "type": "KEY"})
                                pressed[decoded] = True
                    else:
                        if event == b'/x1b':
                            decoded = "KEY_ESCAPE"
                            events.append({"values": (decoded, "KEYDOWN"), "type": "KEY"})
                            pressed[decoded] = True
                        elif decoded := data.decode("utf-8"):
                            if decoded in symb:
                                decoded = symb[decoded].upper()
                            decoded = "KEY_" + decoded
                            events.append({"values": (decoded, "KEYDOWN"), "type": "KEY"})
                            pressed[decoded] = True
                        # print(f"Mouse: {to_name(button)}, ({row}, {col})")
                    # data = sys.stdin.buffer.read(6)
                    # if data.startswith(b"\033[M"):
                    # else:
                    #     events.append({"values": ("KEY_" + data.decode("utf-8"), "KEYDOWN"), "type": "KEY"})

            disable_mouse_tracking()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                # listener.stop()
    finally:
        disable_mouse_tracking()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # listener.stop()


def get_pressed():
    return pressed


class KeyboardEvent:
    def __init__(self, key, event_type):
        self.__key = key
        self.__type = event_type

    @property
    def key(self):
        return self.__key

    @property
    def type(self):
        return self.__type

    @property
    def eventType(self):
        return "KeyboardEvent"

    def __str__(self):
        return f"KeyboardEvent(key={self.key}, type={self.type})"

    def __repr__(self):
        return f"KeyboardEvent(key={self.key}, type={self.type})"

    def __eq__(self, other):
        if not isinstance(other, KeyboardEvent):
            return False
        return self.key == other.key and self.__type == other.type


class MouseEvent:
    def __init__(self, event_type, pos):
        self.__type = event_type
        self.__pos = pos

    @property
    def type(self):
        return self.__type

    @property
    def pos(self):
        return self.__pos

    @property
    def eventType(self):
        return "MouseEvent"

    def __str__(self):
        return f"MouseEvent(type={self.__type}, pos={self.__pos})"

    def __repr__(self):
        return f"MouseEvent(type={self.__type}, pos={self.__pos})"

    def __eq__(self, other):
        if not isinstance(other, MouseEvent):
            return False
        return self.__pos == other.pos and self.__type == other.type


def get():
    ev = []
    for event in events.copy():
        if event["type"] == "KEY":
            ev.append(KeyboardEvent(*event["values"]))
        elif event["type"] == "MOUSE":
            ev.append(MouseEvent(*event["values"]))
    events.clear()
    return ev


th = threading.Thread(target=start, args=(lambda: CLOSED, ))
th.start()
