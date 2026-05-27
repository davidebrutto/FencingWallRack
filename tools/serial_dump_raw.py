#!/usr/bin/env python3
"""Dump serial frames exactly as received, without interpreting fields.

Default behavior matches the legacy reader:
- read_until(expected=b'\x02  \x04')
- print raw bytes (hex) and raw byte-string repr
"""

import argparse
import sys
import time
import serial


def parse_hex_bytes(text: str) -> bytes:
    cleaned = text.replace(" ", "").replace("\\x", "")
    if len(cleaned) % 2 != 0:
        raise ValueError("hex delimiter must contain an even number of digits")
    return bytes.fromhex(cleaned)


def main() -> int:
    parser = argparse.ArgumentParser(description="Raw serial frame dumper")
    parser.add_argument("--port", default="/dev/tty.usbserial-AQ02EBEH", help="Serial port path")
    parser.add_argument("--baud", type=int, default=38400, help="Baud rate")
    parser.add_argument("--bytesize", type=int, default=8, choices=[5, 6, 7, 8], help="Data bits")
    parser.add_argument("--parity", default="N", choices=["N", "E", "O", "M", "S"], help="Parity")
    parser.add_argument("--stopbits", type=float, default=1, choices=[1, 1.5, 2], help="Stop bits")
    parser.add_argument("--timeout", type=float, default=2.0, help="Read timeout (seconds)")
    parser.add_argument(
        "--delimiter",
        default="02202004",
        help="Frame terminator in hex (default: 02 20 20 04)",
    )
    args = parser.parse_args()

    delim = parse_hex_bytes(args.delimiter)

    parity_map = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
        "M": serial.PARITY_MARK,
        "S": serial.PARITY_SPACE,
    }
    stop_map = {
        1: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2: serial.STOPBITS_TWO,
    }

    ser = serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=args.bytesize,
        parity=parity_map[args.parity],
        stopbits=stop_map[args.stopbits],
        timeout=args.timeout,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )

    print(
        f"OPEN {args.port} @ {args.baud} {args.bytesize}{args.parity}{args.stopbits} "
        f"delimiter={delim.hex()} timeout={args.timeout}s"
    )
    print("Press Ctrl+C to stop.\\n")

    try:
        while True:
            frame = ser.read_until(expected=delim)
            if not frame:
                continue

            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] len={len(frame)}")
            print(f"HEX : {frame.hex()}")
            print(f"RAW : {frame!r}")
            try:
                utf8_text = frame.decode("utf-8")
                print(f"UTF8: {utf8_text!r}")
            except UnicodeDecodeError as err:
                utf8_text = frame.decode("utf-8", errors="replace")
                print(f"UTF8: {utf8_text!r}")
                print(f"UTF8_ERR: {err}")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\\nStopped.")
    finally:
        ser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
