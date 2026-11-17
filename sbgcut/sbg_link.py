#!/usr/bin/env python3
"""
sbg_link.py - serial transport + unlock session for the SBG cutter.
Uses pyserial (which Inkscape bundles for its own Plot extension, so it imports fine
inside an Inkscape extension too).
"""
import time
import re

from sbg_protocol import bd9_response, bd12_answer  # noqa: F401  (bd9 used in tests/debug)


class SerialLink:
    def __init__(self, port, baud=115200, timeout=0.1):
        import serial
        self.ser = serial.Serial(port, baud, timeout=timeout)

    def send(self, text, read_reply=True, quiet=0.30, maxwait=3.0):
        data = text.encode("ascii") if isinstance(text, str) else text
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass
        self.ser.write(data)
        self.ser.flush()
        if not read_reply:
            return ""
        buf, t0, last = b"", time.time(), None
        while time.time() - t0 < maxwait:
            self.ser.timeout = 0.1
            chunk = self.ser.read(1)
            chunk += self.ser.read(self.ser.in_waiting or 0)
            if chunk:
                buf += chunk
                last = time.time()
            elif last and time.time() - last >= quiet:
                break
        return buf.decode("ascii", "replace")

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


def _rcmd(reply, n):
    m = re.search(r"RCMD=%d,(\d+)" % n, reply)
    return int(m.group(1)) if m else None


def handshake(link, x=12345):
    """Run BD:9 / BD:10 / BD:12. Returns True on RCMD=12,0 (unlocked)."""
    link.send(";BD:9,%d;" % x)
    reply = link.send(";BD:10;")
    m = re.search(r"RCMD=11,(\d+)", reply)
    if not m:
        raise RuntimeError("no RCMD=11 challenge in reply: %r" % reply)
    c = int(m.group(1))
    reply = link.send("BD:12,%d;" % bd12_answer(c))
    return _rcmd(reply, 12) == 0


def cut(port, job, baud=115200, speed=None, force=None):
    """Open, (optionally set speed/force), unlock, stream the job, close."""
    link = SerialLink(port, baud)
    try:
        link.send(";RCBM;")                      # harmless ping / wake
        if not handshake(link):
            raise RuntimeError("handshake rejected")
        if speed is not None:
            link.send(";BD:100,11,%d;" % int(speed), read_reply=False)
        if force is not None:
            link.send(";BD:100,12,%d;" % int(force), read_reply=False)
        link.send(job, read_reply=False)
    finally:
        link.close()
