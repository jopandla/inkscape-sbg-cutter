#!/usr/bin/env python3
"""
sbgcut.py - Inkscape extension: cut the document (or selection) on an SBG / SKY cutter.

Install: copy this file plus sbg_protocol.py, sbg_link.py and sbgcut.inx into your
Inkscape user extensions folder (Edit > Preferences > System > User extensions),
then restart Inkscape. It appears under Extensions > Export > Cut on SBG plotter.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import inkex
from inkex import bezier

import sbg_protocol as P


class SbgCut(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("--port", default="COM12")
        pars.add_argument("--baud", type=int, default=115200)
        pars.add_argument("--flatness", type=float, default=0.2,
                          help="curve flattening tolerance, mm")
        pars.add_argument("--x", type=float, default=10.0, help="origin X on bed, mm")
        pars.add_argument("--y", type=float, default=10.0, help="origin Y on bed, mm")
        pars.add_argument("--bed_h", type=float, default=180.0, help="bed height, mm")
        pars.add_argument("--flip_y", type=inkex.Boolean, default=True)
        pars.add_argument("--speed", type=int, default=2)
        pars.add_argument("--force", type=int, default=60, help="blade force 30..135 step 15")
        pars.add_argument("--eject", type=float, default=0.0, help="eject feed, mm")
        pars.add_argument("--selection_only", type=inkex.Boolean, default=False)
        pars.add_argument("--dry_run", type=inkex.Boolean, default=False)

    def _flatten(self, element, flat_uu):
        try:
            csp = element.path.transform(element.composed_transform()).to_superpath()
        except Exception:
            return []
        bezier.cspsubdiv(csp, flat_uu)
        out = []
        for sub in csp:
            pts = [(float(p[1][0]), float(p[1][1])) for p in sub]
            if len(pts) >= 2:
                out.append(pts)
        return out

    def collect_polylines(self):
        flat_uu = self.svg.unittouu("%fmm" % self.options.flatness)
        # Build the candidate node list. Groups/Layers are containers: we must NOT
        # emit their .path (it duplicates their children) and we must NOT both descend
        # into them AND visit their children as top-level nodes - either doubles output.
        if self.options.selection_only and len(self.svg.selection):
            nodes = []
            for el in self.svg.selection:
                if isinstance(el, inkex.Group):
                    nodes += list(el.descendants())   # a selected group -> its leaves
                else:
                    nodes.append(el)
        else:
            nodes = list(self.svg.descendants())       # already contains every leaf once
        seen = set()
        polylines_uu = []
        for el in nodes:
            if (isinstance(el, inkex.ShapeElement)
                    and not isinstance(el, inkex.Group)
                    and hasattr(el, "path")
                    and id(el) not in seen):
                seen.add(id(el))
                polylines_uu += self._flatten(el, flat_uu)
        out = []
        for pl in polylines_uu:
            out.append([(self.svg.uutounit(x, "mm"), self.svg.uutounit(y, "mm"))
                        for x, y in pl])
        return out

    def effect(self):
        polylines = self.collect_polylines()
        if not polylines:
            raise inkex.AbortExtension("Nothing to cut (no paths found).")
        job = P.build_job(
            polylines,
            origin_mm=(self.options.x, self.options.y),
            flip_y=self.options.flip_y,
            bed_h_mm=self.options.bed_h,
            eject_mm=self.options.eject,
        )
        if self.options.dry_run:
            fp = os.path.join(tempfile.gettempdir(), "sbgcut_job.txt")
            with open(fp, "w") as f:
                f.write(job)
            inkex.utils.debug("Dry run - job NOT sent.\n%d paths, %d bytes.\nWrote %s"
                              % (len(polylines), len(job), fp))
            return
        try:
            import sbg_link as L
            L.cut(self.options.port, job, baud=self.options.baud,
                  speed=self.options.speed, force=self.options.force)
        except Exception as e:
            raise inkex.AbortExtension("Send failed: %s" % e)


if __name__ == "__main__":
    SbgCut().run()
