#!/usr/bin/env python3
"""Hide the X11 pointer while the monitor kiosk service is running."""

import ctypes
import signal
import sys


def main():
    try:
        x11 = ctypes.CDLL("libX11.so.6")
        xfixes = ctypes.CDLL("libXfixes.so.3")
    except OSError as exc:
        print(f"MONITOR: libreria X11 non disponibile: {exc}", file=sys.stderr)
        return 1

    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xfixes.XFixesQueryVersion.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
    ]
    xfixes.XFixesQueryVersion.restype = ctypes.c_int
    xfixes.XFixesHideCursor.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    xfixes.XFixesShowCursor.argtypes = [ctypes.c_void_p, ctypes.c_ulong]

    display = x11.XOpenDisplay(None)
    if not display:
        print("MONITOR: impossibile collegarsi al display X11", file=sys.stderr)
        return 1

    major, minor = ctypes.c_int(4), ctypes.c_int(0)
    if not xfixes.XFixesQueryVersion(display, ctypes.byref(major), ctypes.byref(minor)) or major.value < 4:
        print("MONITOR: XFixes 4 non disponibile", file=sys.stderr)
        x11.XCloseDisplay(display)
        return 1

    root = x11.XDefaultRootWindow(display)
    xfixes.XFixesHideCursor(display, root)
    x11.XFlush(display)
    print("MONITOR: puntatore X11 nascosto", flush=True)

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while True:
            signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        xfixes.XFixesShowCursor(display, root)
        x11.XFlush(display)
        x11.XCloseDisplay(display)
    return 0


if __name__ == "__main__":
    sys.exit(main())
