#!/usr/bin/env python3
"""
sbg_protocol.py - pure protocol logic for the SBG / SKY "SKY32 Vi" cutter.
No hardware, no serial - just the math and the job encoder, so it is trivially testable.

Everything here was reverse-engineered from the machine's own firmware and verified live.

Handshake (unlock) - two fixed transforms, mod 2**32:
    BD:9  response  Y = (((X + k) ^ k) - k) ^ k      (machine proves itself; X not checked)
    BD:12 answer    Z = (((C ^ k) + k) ^ k) - k      (C = the RCMD=11 challenge)
The four-key tuples below are firmware constants, NOT tied to the serial number, so they are
the same for every unit on this firmware version. A different firmware version may use different
constants - if so, re-extract them and drop them in here.

Job format (what actually cuts):
    IN IN WSJP=<key> <tok> <tok> ... @          (space separated, trailing space)
    tok = U<x>,<y> (pen up / move)  or  D<x>,<y> (pen down / cut)
    - units are 1/40 mm (40 units per mm)
    - every digit of every coordinate is substituted via ENC (keyed by WSJP)
We reuse one WSJP key whose substitution table we know, so ANY coordinates encode correctly.
"""

UNITS_PER_MM = 40
DEFAULT_WSJP = "2026743391"                 # key whose digit table is ENC below (verified)
ENC = {'0':'0','1':'6','2':'4','3':'8','4':'1','5':'2','6':'5','7':'7','8':'3','9':'9'}
MASK = 0xFFFFFFFF

# firmware-extracted handshake constants (add, xor, sub, xor)
BD9_KEYS  = (0x62154517, 0x11251322, 0x23284668, 0x12875121)
BD12_KEYS = (0x187A41F7, 0x33381569, 0x51911241, 0x95514897)


def bd9_response(x, keys=BD9_KEYS):
    a, b, c, d = keys
    r = (x + a) & MASK
    r ^= b
    r = (r - c) & MASK
    r ^= d
    return r & MASK


def bd12_answer(challenge, keys=BD12_KEYS):
    a, b, c, d = keys
    r = (challenge ^ a)
    r = (r + b) & MASK
    r ^= c
    r = (r - d) & MASK
    return r & MASK


def _enc_num(n):
    n = int(round(n))
    sign = '-' if n < 0 else ''
    return sign + ''.join(ENC[ch] for ch in str(abs(n)))


def encode_tokens(tokens):
    """tokens: iterable of (cmd, x_units, y_units) with cmd in {'U','D'}."""
    return ' '.join("%s%s,%s" % (c, _enc_num(x), _enc_num(y)) for c, x, y in tokens)


# blade-prime ticks the stock app always sends first (1 mm then 3 mm), in plain units
PRIME = [('U', 0, 0), ('D', 0, 0), ('D', 0, 40), ('U', 0, 0), ('D', 120, 0)]


def polylines_to_tokens(polylines_mm, origin_mm=(0.0, 0.0), flip_y=False,
                        bed_h_mm=None, eject_mm=0.0, prime=True):
    """
    polylines_mm : list of polylines, each a list of (x_mm, y_mm).
                   first point of each = pen-up move, the rest = pen-down cut.
    origin_mm    : shift the whole drawing so its (0,0) lands here on the bed.
    flip_y       : mirror Y (SVG grows downward; the machine grows upward).
    bed_h_mm     : bed height, required when flip_y is True.
    eject_mm     : after the cut, feed the rollers this many extra mm in +Y to spit the sheet out.
    """
    ox, oy = origin_mm
    tokens = list(PRIME) if prime else []
    max_y = 0
    for pl in polylines_mm:
        pts = []
        for x, y in pl:
            if flip_y:
                if bed_h_mm is None:
                    raise ValueError("flip_y needs bed_h_mm")
                y = bed_h_mm - y
            ux = int(round((x + ox) * UNITS_PER_MM))
            uy = int(round((y + oy) * UNITS_PER_MM))
            pts.append((ux, uy))
            max_y = max(max_y, uy)
        if len(pts) < 2:
            continue
        tokens.append(('U', pts[0][0], pts[0][1]))
        tokens += [('D', x, y) for x, y in pts[1:]]
    if eject_mm > 0:
        feed = max_y + int(round(eject_mm * UNITS_PER_MM))
        tokens.append(('U', 0, feed))     # advance rollers to eject
    tokens.append(('U', 0, 0))
    return tokens


def build_job(polylines_mm, wsjp=DEFAULT_WSJP, **kw):
    tokens = polylines_to_tokens(polylines_mm, **kw)
    return "IN IN WSJP=%s %s @ " % (wsjp, encode_tokens(tokens))
