"""
Build a stand-in bust so the print pipeline can be tested without photos.

Deliberately rough and asymmetric -- a nose, a brow, uneven shoulders -- so
that orientation, splitting and the flat cut are exercised on something that
is not a sphere.

    blender --background --python make_test_head.py -- --out test-head.obj
"""

import argparse
import sys

import bpy


def blob(kind, radius, loc, scale, stiffness=2.0):
    bpy.ops.object.metaball_add(type=kind, radius=radius, location=loc)
    o = bpy.context.object
    o.scale = scale
    o.data.elements[0].stiffness = stiffness
    return o


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="test-head.obj")
    a = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.metaball_add(type='BALL', radius=1.0, location=(0, 0, 1.55))
    base = bpy.context.object
    base.data.resolution = 0.05
    base.scale = (0.82, 1.0, 1.0)

    blob('BALL', 0.55, (0, -0.72, 1.42), (1, 1, 1.15))     # face mass
    blob('BALL', 0.16, (0, -1.12, 1.44), (0.7, 1.3, 0.9))  # nose
    blob('BALL', 0.30, (0, -0.55, 1.80), (1.5, 0.5, 0.5))  # brow
    blob('BALL', 0.45, (0, -0.05, 0.72), (0.9, 0.9, 1.0))  # neck
    blob('BALL', 0.80, (0, -0.05, 0.15), (1.25, 0.85, 0.55)) # shoulders
    blob('BALL', 0.18, (0.48, 0.05, 0.30), (1, 1, 1))      # one shoulder higher

    # convert() needs the base of the metaball family selected AND active;
    # the family is keyed off the object name prefix, so converting the base
    # tessellates every blob added above
    bpy.ops.object.select_all(action='DESELECT')
    base.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    obj.name = "test-head"

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.wm.obj_export(filepath=a.out, export_selected_objects=True,
                          export_materials=False, up_axis='Z', forward_axis='Y')
    print("TEST HEAD", len(obj.data.polygons), "tris ->", a.out)


if __name__ == "__main__":
    main()
