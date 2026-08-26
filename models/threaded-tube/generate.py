"""
Threaded tube + knurled screw cap -- parametric generator.

Deterministic CAD (CadQuery / OpenCascade B-rep), not mesh sculpting: every
dimension below is a real constraint and the thread fit is a computed
clearance rather than a visual guess. Change a number, re-run, get a new
part that is still correct.

Target: Bambu Lab A1 Mini, PLA, 0.4 mm nozzle, 0.20 mm layer height.

    python3 generate.py [--outdir DIR]

Writes STL (print-ready orientation) and STEP (re-editable CAD) per part.
"""

import argparse
import os

import cadquery as cq

# ---------------------------------------------------------------- parameters
BORE = 15.5          # internal cavity diameter
BODY_H = 58.0        # body total height (closed bottom -> neck top)
BOTTOM = 1.8         # closed bottom thickness
NECK_H = 12.0        # threaded neck length at the top of the body

THREAD_MAJOR = 20.0  # male thread major diameter == body outer diameter
PITCH = 2.5          # coarse pitch: closes in ~4 turns, robust in FDM
DEPTH = 1.0          # radial thread depth
RAD_CLEAR = 0.2      # radial clearance per flank (one layer width-ish)
MALE_ROOT, MALE_CREST = 1.7, 0.6    # male trapezoid axial widths
FEM_ROOT, FEM_CREST = 1.6, 0.5      # female narrower -> ~0.2 mm axial play

CAP_WALL = 1.8
CAP_TOP = 2.0
CAP_H = 15.0
KNURL_N = 24         # vertical flutes around the skirt
KNURL_D = 1.8        # flute cutter diameter
KNURL_DEPTH = 0.6

OVERLAP = 0.15       # thread root sunk into the core it fuses to
FUZZ = 1e-4          # fuzzy-boolean tolerance -- see _fuse()
SEG_TOL, ANG_TOL = 0.008, 0.1       # STL tessellation quality

# ------------------------------------------------------------------ derived
R_MAJOR = THREAD_MAJOR / 2.0            # 10.0  male crest
R_CORE = R_MAJOR - DEPTH                # 9.0   male root
R_FEM_MAJOR = R_MAJOR + RAD_CLEAR       # 10.2  cap cavity wall
R_FEM_MINOR = R_FEM_MAJOR - DEPTH       # 9.2   female crest
R_ENV_OUT = R_FEM_MAJOR + OVERLAP + 0.1
CAP_OD = 2 * (R_FEM_MAJOR + CAP_WALL)   # 24.0
CAP_CAVITY = CAP_H - CAP_TOP            # 13.0
NECK_Z0 = BODY_H - NECK_H               # 46.0
ASSEMBLED_H = BODY_H + CAP_TOP          # 60.0


def _fuse(a, b):
    """Fuse two solids with a fuzzy tolerance.

    A helical swept solid meets its core along a long tangential seam, and
    OpenCascade's exact boolean quietly returns the first operand unchanged
    there -- no exception, just a missing thread. A small fuzzy value makes
    the intersection robust. Same reason _clip() below is fuzzy.
    """
    return a.fuse(b, tol=FUZZ).clean()


def _clip(a, b):
    return a.intersect(b, tol=FUZZ).clean()


def _thread(base_r, depth, root_w, crest_w, z0, length, inward=False):
    """One helical trapezoidal ridge, swept along a helix, as a solid.

    The profile root is sunk OVERLAP mm into the part it will fuse to: a
    ridge merely tangent to the core has no volume to fuse through.
    """
    sign = -1.0 if inward else 1.0
    tip = base_r + sign * depth
    tail = base_r - sign * OVERLAP
    pts = [
        (tail, -root_w / 2.0),
        (base_r, -root_w / 2.0),
        (tip, -crest_w / 2.0),
        (tip, crest_w / 2.0),
        (base_r, root_w / 2.0),
        (tail, root_w / 2.0),
    ]
    # over-run one pitch at each end so the taper envelope always has material
    helix = cq.Wire.makeHelix(PITCH, length + 2 * PITCH, base_r)
    profile = cq.Workplane("XZ").polyline(pts).close()
    return profile.sweep(cq.Workplane(obj=helix), isFrenet=True).val().translate(
        (0, 0, z0 - PITCH)
    )


def _revolve(points):
    """Solid of revolution from (radius, z) points, about the Z axis.

    revolve() takes its axis in workplane-local coordinates: on the XZ plane
    the local Y axis is the global Z axis.
    """
    return (
        cq.Workplane("XZ")
        .polyline(points)
        .close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
        .val()
    )


def body():
    """Tube with a closed bottom and an external thread on the neck."""
    core = (
        cq.Workplane("XY")
        .circle(R_MAJOR)
        .extrude(NECK_Z0)                     # plain barrel, Ø20
        .faces(">Z")
        .workplane()
        .circle(R_CORE)
        .extrude(NECK_H)                      # neck core, Ø18
        .faces(">Z")
        .workplane()
        .circle(BORE / 2.0)
        .cutBlind(-(BODY_H - BOTTOM))         # bore, leaving the closed bottom
        .val()
    )

    z0, tlen = NECK_Z0 + 0.5, NECK_H - 2.0    # thread run, clear of both ends
    ridge = _thread(R_CORE, DEPTH, MALE_ROOT, MALE_CREST, z0, tlen)

    # envelope: crests fade out over ~1 mm at each end instead of stopping dead
    env = (
        cq.Workplane("XY", origin=(0, 0, z0 - 0.4))
        .circle(R_MAJOR)
        .extrude(tlen + 0.8)
        .edges("%Circle")
        .chamfer(DEPTH * 0.95)
        .val()
    )
    res = cq.Workplane(obj=_fuse(core, _clip(ridge, env)))

    top = cq.selectors.BoxSelector((-11, -11, BODY_H - 0.1), (11, 11, BODY_H + 0.1))
    return (
        res.edges(top).chamfer(0.5)           # lead-in on the neck rim
        .faces("<Z").edges().chamfer(0.6)     # bottom edge: no elephant foot
    )


def cap():
    """Knurled cap with an internal thread, in use orientation (opening down)."""
    c = cq.Workplane("XY").circle(CAP_OD / 2.0).extrude(CAP_H)

    cutter_r = KNURL_D / 2.0
    flutes = (
        cq.Workplane("XY", origin=(0, 0, -1))
        .polarArray(CAP_OD / 2.0 + cutter_r - KNURL_DEPTH, 0, 360, KNURL_N)
        .circle(cutter_r)
        .extrude(CAP_H - 1.2)                 # leave a smooth top band
    )
    c = c.cut(flutes).faces(">Z").edges().chamfer(0.8)
    c = c.faces("<Z").workplane().circle(R_FEM_MAJOR).cutBlind(-CAP_CAVITY).val()

    ridge = _thread(
        R_FEM_MAJOR, DEPTH, FEM_ROOT, FEM_CREST, 1.2, CAP_CAVITY - 2.4, inward=True
    )
    # envelope: an annulus whose inner wall flares out over 1 mm at each end,
    # so the first and last turns fade. Every radius is offset off the ridge
    # and envelope surfaces -- coincident faces are what break booleans.
    zt, ht = 0.8, CAP_CAVITY - 1.6
    plug = _revolve(
        [
            (0, zt),
            (R_ENV_OUT + 0.3, zt),
            (R_FEM_MINOR - 0.1, zt + 1.0),
            (R_FEM_MINOR - 0.1, zt + ht - 1.0),
            (R_ENV_OUT + 0.3, zt + ht),
            (0, zt + ht),
        ]
    )
    env = (
        cq.Workplane("XY", origin=(0, 0, zt))
        .circle(R_ENV_OUT)
        .extrude(ht)
        .val()
        .cut(plug)
    )
    c = _fuse(c, _clip(ridge, env))

    # conical mouth: lets the cap find the neck instead of cross-threading
    mouth = _revolve(
        [(R_FEM_MAJOR, 0), (R_FEM_MAJOR + 0.9, 0), (R_FEM_MAJOR, 0.9)]
    )
    return cq.Workplane(obj=c.cut(mouth))


def for_printing(shape, flip):
    """Drop a part onto the bed, flipped if it prints better upside down."""
    s = shape.rotate((0, 0, 0), (1, 0, 0), 180) if flip else shape
    bb = s.BoundingBox()
    return s.translate((0, 0, -bb.zmin))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    # the cap prints closed-top-down: no ceiling to bridge over the cavity
    parts = (
        ("tube-body", body().val(), False),
        ("tube-cap", cap().val(), True),
    )
    for name, shape, flip in parts:
        out = for_printing(shape, flip)
        for ext in ("stl", "step"):
            cq.exporters.export(
                out,
                os.path.join(args.outdir, f"{name}.{ext}"),
                tolerance=SEG_TOL,
                angularTolerance=ANG_TOL,
            )
        bb = out.BoundingBox()
        print(
            f"{name:10s} {shape.Volume()/1000:5.2f} cm3  "
            f"bbox {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm  "
            f"solid={out.isValid()}"
        )


if __name__ == "__main__":
    main()
