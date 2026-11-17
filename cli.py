#!/usr/bin/env python3
"""
sbg-cut CLI - cut an SVG or DXF on the SBG / SKY cutter without Inkscape.

    python cli.py drawing.svg --at 20,30 --dry          # build job, don't send
    python cli.py drawing.dxf --at 20,30 --port COM12    # unlock + cut
    python cli.py --square 10 --port COM12               # quick test square

SVG support is intentionally simple (M/L/H/V/C/Q/Z, flattened); for anything with
transforms, text, clones or units other than mm, use the Inkscape extension instead -
it uses Inkscape's own geometry engine. DXF covers LINE, LWPOLYLINE, CIRCLE, ARC.
"""
import argparse, math, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sbgcut"))
import sbg_protocol as P


def _flatten_cubic(p0, p1, p2, p3, tol, out):
    # adaptive subdivision
    def rec(a, b, c, d, depth):
        if depth > 18:
            out.append(d); return
        # flatness: distance of control points from chord
        ux = 3*b[0]-2*a[0]-d[0]; uy = 3*b[1]-2*a[1]-d[1]
        vx = 3*c[0]-a[0]-2*d[0]; vy = 3*c[1]-a[1]-2*d[1]
        if max(ux*ux, vx*vx) + max(uy*uy, vy*vy) <= 16*tol*tol:
            out.append(d); return
        ab=((a[0]+b[0])/2,(a[1]+b[1])/2); bc=((b[0]+c[0])/2,(b[1]+c[1])/2); cd=((c[0]+d[0])/2,(c[1]+d[1])/2)
        abc=((ab[0]+bc[0])/2,(ab[1]+bc[1])/2); bcd=((bc[0]+cd[0])/2,(bc[1]+cd[1])/2)
        m=((abc[0]+bcd[0])/2,(abc[1]+bcd[1])/2)
        rec(a,ab,abc,m,depth+1); rec(m,bcd,cd,d,depth+1)
    rec(p0,p1,p2,p3,0)


def parse_svg(path, tol=0.2):
    data = open(path, "r", errors="ignore").read()
    # NOTE: assumes user units == mm (no transform handling). Use Inkscape for the rest.
    polylines = []
    for d in re.findall(r'\bd\s*=\s*"([^"]+)"', data):
        toks = re.findall(r'[MmLlHhVvCcSsQqTtZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?', d)
        i = 0; cur = (0.0, 0.0); start = (0.0, 0.0); pl = []; cmd = None
        def num():
            nonlocal i; v = float(toks[i]); i += 1; return v
        while i < len(toks):
            if re.match(r'[A-Za-z]', toks[i]): cmd = toks[i]; i += 1
            rel = cmd.islower(); C = cmd.upper()
            if C == 'M':
                x = num(); y = num(); cur = (cur[0]+x, cur[1]+y) if rel else (x, y)
                if pl: polylines.append(pl)
                pl = [cur]; start = cur; cmd = 'l' if rel else 'L'
            elif C == 'L':
                x = num(); y = num(); cur = (cur[0]+x, cur[1]+y) if rel else (x, y); pl.append(cur)
            elif C == 'H':
                x = num(); cur = (cur[0]+x, cur[1]) if rel else (x, cur[1]); pl.append(cur)
            elif C == 'V':
                y = num(); cur = (cur[0], cur[1]+y) if rel else (cur[0], y); pl.append(cur)
            elif C == 'C':
                c1=(num(),num()); c2=(num(),num()); e=(num(),num())
                if rel: c1=(cur[0]+c1[0],cur[1]+c1[1]); c2=(cur[0]+c2[0],cur[1]+c2[1]); e=(cur[0]+e[0],cur[1]+e[1])
                _flatten_cubic(cur,c1,c2,e,tol,pl); cur=e
            elif C == 'Q':
                q=(num(),num()); e=(num(),num())
                if rel: q=(cur[0]+q[0],cur[1]+q[1]); e=(cur[0]+e[0],cur[1]+e[1])
                c1=(cur[0]+2/3*(q[0]-cur[0]),cur[1]+2/3*(q[1]-cur[1]))
                c2=(e[0]+2/3*(q[0]-e[0]),e[1]+2/3*(q[1]-e[1]))
                _flatten_cubic(cur,c1,c2,e,tol,pl); cur=e
            elif C == 'Z':
                pl.append(start); cur = start
            else:
                i += 1  # skip S/T (unsupported smooth) args conservatively
        if pl: polylines.append(pl)
    return polylines


def _arc(cx, cy, r, a0, a1, tol):
    n = max(8, int(abs(a1-a0)*r/max(tol,1e-3)))
    return [(cx+r*math.cos(a0+(a1-a0)*k/n), cy+r*math.sin(a0+(a1-a0)*k/n)) for k in range(n+1)]


def parse_dxf(path, tol=0.2):
    L = [l.rstrip("\r\n") for l in open(path, errors="ignore")]
    pr = [(L[i].strip(), L[i+1].strip()) for i in range(0, len(L)-1, 2)]
    ents = []; cur = None; sec = None; after = False
    for c, v in pr:
        if c == "0":
            if cur and sec == "ENTITIES": ents.append(cur)
            cur = None
            if v in ("ENDSEC", "EOF"): sec = None
            elif v == "SECTION": after = True
            elif sec == "ENTITIES": cur = {"t": v, "d": []}
        elif after and c == "2": sec = v; after = False
        elif cur is not None: cur["d"].append((c, v))
    def g(d, k, dv=0.0):
        for c, v in d:
            if c == k:
                try: return float(v)
                except: pass
        return dv
    out = []; i = 0
    while i < len(ents):
        e = ents[i]; t = e["t"]; d = e["d"]; i += 1
        if t == "LINE": out.append([(g(d,"10"),g(d,"20")),(g(d,"11"),g(d,"21"))])
        elif t == "CIRCLE": out.append(_arc(g(d,"10"),g(d,"20"),g(d,"40"),0,2*math.pi,tol))
        elif t == "ARC":
            a0=math.radians(g(d,"50")); a1=math.radians(g(d,"51"))
            if a1<=a0: a1+=2*math.pi
            out.append(_arc(g(d,"10"),g(d,"20"),g(d,"40"),a0,a1,tol))
        elif t == "LWPOLYLINE":
            xs=[float(v) for c,v in d if c=="10"]; ys=[float(v) for c,v in d if c=="20"]
            pts=list(zip(xs,ys))
            if int(g(d,"70",0))&1 and pts: pts.append(pts[0])
            if len(pts)>=2: out.append(pts)
    return out


def main():
    ap = argparse.ArgumentParser(description="cut SVG/DXF on the SBG cutter")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--square", type=float, help="skip the file; cut an NxN mm test square")
    ap.add_argument("--at", default="10,10", help="origin X,Y in mm")
    ap.add_argument("--flatness", type=float, default=0.2)
    ap.add_argument("--flip-y", action="store_true")
    ap.add_argument("--bed-h", type=float, default=180.0)
    ap.add_argument("--eject", type=float, default=0.0)
    ap.add_argument("--port"); ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--speed", type=int, default=2); ap.add_argument("--force", type=int, default=60)
    ap.add_argument("--dry", action="store_true", help="print job, do not send")
    a = ap.parse_args()
    at = tuple(float(v) for v in a.at.split(","))

    if a.square:
        s = a.square
        polylines = [[(0,0),(s,0),(s,s),(0,s),(0,0)]]
    elif a.file and a.file.lower().endswith(".dxf"):
        polylines = parse_dxf(a.file, a.flatness)
    elif a.file and a.file.lower().endswith(".svg"):
        polylines = parse_svg(a.file, a.flatness)
    else:
        ap.error("give an .svg/.dxf file or --square N")
    if not polylines:
        ap.error("nothing to cut")

    job = P.build_job(polylines, origin_mm=at, flip_y=a.flip_y,
                      bed_h_mm=a.bed_h, eject_mm=a.eject)
    print("%d paths, job %d bytes" % (len(polylines), len(job)))
    if a.dry or not a.port:
        print(job)
        if not a.port and not a.dry:
            print("(no --port given; not sending)")
        return
    import sbg_link as L
    L.cut(a.port, job, baud=a.baud, speed=a.speed, force=a.force)
    print("sent.")


if __name__ == "__main__":
    main()
