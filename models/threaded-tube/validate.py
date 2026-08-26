"""
Validation for the threaded tube. Run after generate.py.

Two things get checked, because "it looked right" is how unprintable models
happen:

1. Mesh health per part -- watertight, consistent winding, positive volume,
   expected bounding box. Bambu Studio's auto-repair is not a workflow.
2. Virtual assembly -- the cap is screwed onto the body in software and the
   solid intersection is measured. If the threads interfere, this reports a
   collision volume; if they mesh, it reports ~0 at the correct phase.

    python3 validate.py
"""

import math
import sys

import numpy as np
import trimesh

import generate as g

TOL = 0.02  # mm, mesh/measurement tolerance


def to_mesh(shape):
    verts, tris = shape.tessellate(g.SEG_TOL, g.ANG_TOL)
    m = trimesh.Trimesh(
        vertices=np.array([(v.x, v.y, v.z) for v in verts]),
        faces=np.array(tris),
        process=True,
    )
    m.merge_vertices()
    m.fix_normals()
    return m


def check_part(name, mesh, expect_bbox, expect_vol_cm3):
    ext = mesh.bounding_box.extents
    ok = []
    ok.append(("watertight", mesh.is_watertight, mesh.is_watertight))
    ok.append(("winding consistent", mesh.is_winding_consistent,
               mesh.is_winding_consistent))
    ok.append(("positive volume", mesh.volume > 0, f"{mesh.volume/1000:.2f} cm3"))
    ok.append(("single shell", mesh.body_count == 1, mesh.body_count))
    bbox_ok = all(abs(a - b) < 0.05 for a, b in zip(ext, expect_bbox))
    ok.append(("bbox matches spec", bbox_ok,
               " x ".join(f"{e:.2f}" for e in ext)))
    vol_ok = abs(mesh.volume / 1000 - expect_vol_cm3) < 0.05
    ok.append(("volume matches spec", vol_ok, f"{mesh.volume/1000:.2f} cm3"))

    print(f"\n{name}  ({len(mesh.faces)} triangles)")
    for label, passed, value in ok:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label:22s} {value}")
    return all(p for _, p, _ in ok)


def screw_test(body_mesh, cap_mesh, steps=60):
    """Screw the cap on and look for interference.

    The cap is placed at its seated height, then rotated through a full turn.
    A thread pair that meshes has one phase per turn where the two solids
    only touch; anything else means the flanks collide.
    """
    seated_z = g.BODY_H - g.CAP_CAVITY
    results = []
    for i in range(steps):
        theta = 360.0 * i / steps
        c = cap_mesh.copy()
        c.apply_transform(trimesh.transformations.rotation_matrix(
            math.radians(theta), (0, 0, 1)))
        c.apply_translation((0, 0, seated_z))
        try:
            inter = trimesh.boolean.intersection([body_mesh, c], engine="manifold")
            vol = 0.0 if inter.is_empty else abs(inter.volume)
        except Exception:
            vol = float("nan")
        results.append((theta, vol))

    best_theta, best_vol = min(results, key=lambda r: r[1])
    worst = max(v for _, v in results)
    print("\nvirtual assembly (cap screwed onto body, seated)")
    print(f"  best phase          {best_theta:.0f} deg")
    print(f"  interference there  {best_vol:.3f} mm3")
    print(f"  worst phase         {worst:.1f} mm3  (flanks colliding, as expected)")
    passed = best_vol < 1.0
    print(f"  [{'PASS' if passed else 'FAIL'}] threads mesh without interference")
    return passed


def main():
    body, cap = g.body().val(), g.cap().val()
    bm, cm = to_mesh(body), to_mesh(cap)

    ok = check_part("tube-body", bm, (20.02, 20.02, 58.01), 7.15)
    ok &= check_part("tube-cap", cm, (24.02, 24.01, 15.02), 2.53)
    ok &= screw_test(bm, cm)

    print("\nfit summary")
    print(f"  thread            M{g.THREAD_MAJOR:.0f} x {g.PITCH} trapezoidal, "
          f"single start, right hand")
    print(f"  radial clearance  {g.RAD_CLEAR:.2f} mm per flank")
    print(f"  axial clearance   {(g.MALE_ROOT - g.FEM_ROOT):.2f} mm")
    print(f"  turns to close    {(g.NECK_H - 2.0) / g.PITCH:.1f}")
    print(f"  thinnest wall     {(g.THREAD_MAJOR - 2 * g.DEPTH - g.BORE) / 2:.2f} mm "
          f"(neck), min printable 1.20 mm")
    print(f"  capacity          "
          f"{math.pi * (g.BORE/2)**2 * (g.BODY_H - g.BOTTOM) / 1000:.1f} mL")
    print(f"  assembled height  {g.ASSEMBLED_H:.1f} mm")

    print("\n" + ("ALL CHECKS PASSED" if ok else "CHECKS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
