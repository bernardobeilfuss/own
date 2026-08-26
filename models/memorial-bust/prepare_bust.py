"""
Turn a reconstructed head mesh into a printable memorial bust.

This is the half of the job that does not depend on how the head was
reconstructed. Feed it any mesh -- photogrammetry, Tripo, a sculpt -- and it
returns print-ready STLs: upright, scaled, watertight, flat on the bed, on a
plinth with the name engraved, split into sections if it exceeds the build
volume.

Run under Blender, which does the heavy geometry:

    blender --background --python prepare_bust.py -- --input head.obj \
        --name "Maria Silva" --dates "1948 - 2024" --height 150

Then check the result with validate_bust.py.
"""

import argparse
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

BED = 180.0          # A1 Mini build volume, mm
VOXEL = 0.6          # remesh voxel size, mm -- detail floor for a 0.4 nozzle
PIN_D = 6.0          # alignment dowel diameter
PIN_CLEAR = 0.25     # dowel hole clearance, radial


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Blender works in metres; a 150 mm bust in metre units is a rounding
    # error away from the clipping planes, so drive the scene in millimetres
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 0.001


def load(path):
    ext = os.path.splitext(path)[1].lower()
    # Take the file's axes literally. Blender's OBJ and PLY importers default
    # to treating the file as Y-up and rotating it, which lands a bust on its
    # back -- and then --height scales by its depth. Rotation is --y-up's job,
    # where it is a decision instead of a surprise.
    loaders = {
        ".obj": lambda p: bpy.ops.wm.obj_import(
            filepath=p, forward_axis='Y', up_axis='Z'),
        ".ply": lambda p: bpy.ops.wm.ply_import(
            filepath=p, forward_axis='Y', up_axis='Z'),
        ".stl": lambda p: bpy.ops.import_mesh.stl(
            filepath=p, axis_forward='Y', axis_up='Z'),
        ".glb": lambda p: bpy.ops.import_scene.gltf(filepath=p),
        ".gltf": lambda p: bpy.ops.import_scene.gltf(filepath=p),
        ".fbx": lambda p: bpy.ops.import_scene.fbx(filepath=p),
    }
    if ext not in loaders:
        sys.exit(f"unsupported input: {ext}")
    loaders[ext](path)

    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        sys.exit("no mesh in input file")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def upright(obj, y_up):
    """Most photogrammetry and image-to-3D output is Y-up; the bed is Z-up."""
    if y_up:
        obj.rotation_euler = (math.radians(90), 0, 0)
        bpy.ops.object.transform_apply(rotation=True)


def scale_to_height(obj, height_mm):
    dims = obj.dimensions
    if dims.z < max(dims.x, dims.y):
        print(f"warning: the mesh is wider ({max(dims.x, dims.y):.1f}) than it "
              f"is tall ({dims.z:.1f}) -- a bust normally is not. If it came "
              f"out of photogrammetry it is probably lying down: pass --y-up.")
    if dims.z <= 0:
        sys.exit("input mesh has no height")
    obj.scale *= height_mm / dims.z
    bpy.ops.object.transform_apply(scale=True)
    # sit on the bed, centred in X and Y
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    obj.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    bpy.ops.object.transform_apply(location=True)


def fit_footprint(obj, bed, allow_scale):
    """A bust is wider than it is deep, and shoulders are the widest part.

    Splitting only in Z, as this script does, cannot rescue a model whose
    footprint overruns the bed -- so measure it and say so, loudly, instead
    of exporting something that will not slice.
    """
    d = obj.dimensions
    over = max(d.x, d.y) - bed
    if over <= 0:
        return 0.0
    if not allow_scale:
        return over
    factor = (bed - 1.0) / max(d.x, d.y)
    obj.scale *= factor
    bpy.ops.object.transform_apply(scale=True)
    return 0.0


def make_solid(obj, voxel):
    """Voxel remesh: the one reliable way to make scan output watertight.

    Photogrammetry and image-to-3D meshes arrive with holes, self-intersections
    and inverted normals. Repairing those individually is a losing game;
    resampling the volume is not. The cost is detail below the voxel size,
    which for a 0.4 mm nozzle is detail that could not print anyway.
    """
    m = obj.modifiers.new("remesh", 'REMESH')
    m.mode = 'VOXEL'
    m.voxel_size = voxel
    m.use_smooth_shade = False
    bpy.ops.object.modifier_apply(modifier=m.name)


def decimate(obj, target_tris):
    """Voxel remesh is generous: 0.6 mm voxels over a 150 mm bust run past
    half a million triangles, which is a 50 MB STL the slicer has to chew
    through for detail no nozzle will render. Collapse to a sane budget."""
    have = len(obj.data.polygons)
    if have <= target_tris:
        return have
    m = obj.modifiers.new("decimate", 'DECIMATE')
    m.ratio = target_tris / have
    bpy.ops.object.modifier_apply(modifier=m.name)
    return len(obj.data.polygons)


def cut_below(obj, z):
    """Slice off everything under z with a boolean, leaving a flat face."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.object
    box.scale = (BED * 4, BED * 4, BED * 4)
    box.location = (0, 0, z - BED * 2)
    bpy.ops.object.transform_apply(location=True, scale=True)

    bpy.context.view_layer.objects.active = obj
    m = obj.modifiers.new("cut", 'BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.object = box
    m.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(box, do_unlink=True)


def add_plinth(obj, name, dates, height, chamfer=1.5):
    """A plinth wide enough to stand on, with the name cut into the front."""
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    w = max(max(v.x for v in bb) - min(v.x for v in bb),
            max(v.y for v in bb) - min(v.y for v in bb))
    side = w * 1.15

    bpy.ops.mesh.primitive_cube_add(size=1)
    p = bpy.context.object
    p.name = "plinth"
    p.scale = (side, side * 0.75, height)
    p.location = (0, 0, -height / 2.0)
    bpy.ops.object.transform_apply(location=True, scale=True)

    bev = p.modifiers.new("bevel", 'BEVEL')
    bev.width = chamfer
    bev.segments = 3
    bpy.ops.object.modifier_apply(modifier=bev.name)

    if name or dates:
        engrave(p, name, dates, side, height)

    # lift everything so the plinth base sits at z = 0
    for o in (obj, p):
        o.location.z += height
    bpy.ops.object.select_all(action='DESELECT')
    for o in (obj, p):
        o.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True)
    return p


def engrave(plinth, name, dates, side, height, depth=0.8, min_cap=6.0):
    """Cut the text into the plinth front.

    Engraved rather than raised: a raised serif this small would come off the
    bed. 0.8 mm deep is two nozzle widths, legible without a second colour.

    Text size comes from the plinth face, not from a guess. A 0.4 mm nozzle
    needs roughly 6 mm of cap height before the strokes of a normal typeface
    reach the 0.7 mm that will actually render -- below that the letters fill
    in and the name turns to mush, so say so rather than engrave noise.
    """
    lines = [t for t in (name, dates) if t]
    lead = height / (len(lines) + 0.9)          # one line-height per line, plus margin
    widest = max(len(t) for t in lines)
    size = min(lead * 0.66, side * 0.78 / (widest * 0.60))
    if size < min_cap:
        print(f"warning: the plinth only allows {size:.1f} mm caps for "
              f"{len(lines)} lines; below {min_cap:.0f} mm the strokes are "
              f"thinner than the nozzle can resolve. Raise --plinth to "
              f"{math.ceil(height * min_cap / size)} mm, or engrave fewer "
              f"lines.")

    top = -height / 2.0 + lead * (len(lines) - 1) / 2.0
    cutters = []
    for i, text in enumerate(lines):
        bpy.ops.object.text_add()
        t = bpy.context.object
        t.data.body = text
        t.data.size = size
        t.data.align_x = 'CENTER'
        t.data.align_y = 'CENTER'
        t.data.extrude = depth * 2
        t.rotation_euler = (math.radians(90), 0, 0)
        t.location = (0, -side * 0.375 - depth, top - i * lead)
        bpy.ops.object.convert(target='MESH')
        cutters.append(bpy.context.object)

    bpy.ops.object.select_all(action='DESELECT')
    for c in cutters:
        c.select_set(True)
    bpy.context.view_layer.objects.active = cutters[0]
    if len(cutters) > 1:
        bpy.ops.object.join()
    cutter = bpy.context.object

    bpy.context.view_layer.objects.active = plinth
    m = plinth.modifiers.new("text", 'BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.object = cutter
    m.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def join_all(objs, name="bust"):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    # union the overlap so head and plinth become one closed volume
    m = obj.modifiers.new("weld", 'REMESH')
    m.mode = 'VOXEL'
    m.voxel_size = VOXEL
    m.use_smooth_shade = False
    bpy.ops.object.modifier_apply(modifier=m.name)
    return obj


def hollow(obj, wall, drain_d=6.0):
    """Shell the model. For resin only -- on FDM let the slicer do infill."""
    m = obj.modifiers.new("shell", 'SOLIDIFY')
    m.thickness = wall
    m.offset = 1.0
    m.use_even_offset = True
    bpy.ops.object.modifier_apply(modifier=m.name)

    bpy.ops.mesh.primitive_cylinder_add(radius=drain_d / 2, depth=wall * 6)
    d = bpy.context.object
    d.location = (0, 0, wall)
    bpy.ops.object.transform_apply(location=True)
    bpy.context.view_layer.objects.active = obj
    b = obj.modifiers.new("drain", 'BOOLEAN')
    b.operation = 'DIFFERENCE'
    b.object = d
    b.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=b.name)
    bpy.data.objects.remove(d, do_unlink=True)


def split(obj, bed, pin_d=PIN_D, margin=2.0):
    """Cut into bed-height sections with dowel holes for alignment.

    Holes in both faces plus a separate printed dowel, rather than a boss on
    one half: a printed boss carries layer lines across the joint and snaps.
    """
    total = obj.dimensions.z
    n = math.ceil(total / (bed - margin))
    if n < 2:
        return [obj], 0.0

    step = total / n
    parts = []
    for i in range(n):
        z0, z1 = i * step, (i + 1) * step
        piece = obj.copy()
        piece.data = obj.data.copy()
        piece.name = f"bust-{i + 1}of{n}"
        bpy.context.collection.objects.link(piece)

        bpy.context.view_layer.objects.active = piece
        if i > 0:
            cut_below(piece, z0)
        if i < n - 1:
            cut_above(piece, z1)

        for z, up in ((z0, True), (z1, False)):
            if 0 < z < total:
                drill_pins(piece, z, pin_d, up)
        piece.location.z -= z0
        bpy.ops.object.transform_apply(location=True)
        parts.append(piece)

    bpy.data.objects.remove(obj, do_unlink=True)
    return parts, step


def cut_above(obj, z):
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.object
    box.scale = (BED * 4, BED * 4, BED * 4)
    box.location = (0, 0, z + BED * 2)
    bpy.ops.object.transform_apply(location=True, scale=True)
    bpy.context.view_layer.objects.active = obj
    m = obj.modifiers.new("cut", 'BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.object = box
    m.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(box, do_unlink=True)


def drill_pins(obj, z, pin_d, going_up, depth=8.0, count=2, spread=0.45):
    """Two holes, off-centre, so the joint can only close one way round."""
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    half = (max(v.x for v in bb) - min(v.x for v in bb)) * spread * 0.5
    r = pin_d / 2 + PIN_CLEAR
    cutters = []
    for i in range(count):
        x = half * (1 if i else -1) * (0.8 if i else 1.0)   # asymmetric on purpose
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth * 2)
        c = bpy.context.object
        c.location = (x, 0, z + (depth if going_up else -depth))
        bpy.ops.object.transform_apply(location=True)
        cutters.append(c)

    bpy.ops.object.select_all(action='DESELECT')
    for c in cutters:
        c.select_set(True)
    bpy.context.view_layer.objects.active = cutters[0]
    bpy.ops.object.join()
    cutter = bpy.context.object

    bpy.context.view_layer.objects.active = obj
    m = obj.modifiers.new("pins", 'BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.object = cutter
    m.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def make_dowel(pin_d, length):
    bpy.ops.mesh.primitive_cylinder_add(radius=pin_d / 2, depth=length, vertices=64)
    d = bpy.context.object
    d.name = "dowel"
    d.location = (0, 0, length / 2)
    bpy.ops.object.transform_apply(location=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bevel(offset=0.4, segments=2, affect='EDGES')
    bpy.ops.object.mode_set(mode='OBJECT')
    return d


def export(obj, path):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_mesh.stl(filepath=path, use_selection=True,
                            global_scale=1.0, ascii=False)


def stats(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    vol = bm.calc_volume(signed=True)
    area = sum(f.calc_area() for f in bm.faces)
    closed = all(e.is_manifold for e in bm.edges)
    bm.free()
    return vol, area, closed, len(obj.data.polygons)


def filament_grams(vol_mm3, area_mm2, walls=3, line=0.42, infill=0.10,
                   density=1.24):
    """Rough PLA mass: solid shell plus infill through what is left.

    An estimate, not a slicer. Bambu Studio's number is the one to trust;
    this exists so nobody is surprised by the order of magnitude.
    """
    shell = min(area_mm2 * walls * line, vol_mm3)
    return (shell + (vol_mm3 - shell) * infill) * density / 1000.0


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--name", default="")
    ap.add_argument("--dates", default="")
    ap.add_argument("--height", type=float, default=150.0,
                    help="head height in mm, excluding the plinth")
    ap.add_argument("--plinth", type=float, default=26.0,
                    help="plinth height in mm; 0 to omit. Two lines of\n"
                         "engraving need about 26 mm to stay legible.")
    ap.add_argument("--voxel", type=float, default=VOXEL)
    ap.add_argument("--bed", type=float, default=BED)
    ap.add_argument("--hollow", type=float, default=0.0,
                    help="shell thickness in mm; resin only, leave 0 for FDM")
    ap.add_argument("--y-up", action="store_true",
                    help="input is Y-up (most photogrammetry output)")
    ap.add_argument("--tris", type=int, default=200000,
                    help="triangle budget per part")
    ap.add_argument("--fit-bed", action="store_true",
                    help="scale down if the shoulders overrun the bed")
    a = ap.parse_args(argv)

    clean_scene()
    obj = load(a.input)
    upright(obj, a.y_up)
    scale_to_height(obj, a.height)
    make_solid(obj, a.voxel)
    cut_below(obj, 0.0)

    pieces = [obj]
    if a.plinth > 0:
        p = add_plinth(obj, a.name, a.dates, a.plinth)
        pieces = [obj, p]
    obj = join_all(pieces)

    # only now is the footprint final: the plinth is wider than the head
    asked_h = obj.dimensions.z
    over = fit_footprint(obj, a.bed, a.fit_bed)
    if over > 0:
        sys.exit(
            f"\nfootprint is {over:.0f} mm wider than the {a.bed:.0f} mm bed "
            f"({obj.dimensions.x:.0f} x {obj.dimensions.y:.0f} mm, plinth "
            f"included).\nThis script splits in Z only, so it cannot rescue "
            f"that.\nEither lower --height, or pass --fit-bed to scale to fit."
        )
    if obj.dimensions.z < asked_h - 0.5:
        print(f"note: --fit-bed scaled the bust down to fit the bed, "
              f"{asked_h:.0f} -> {obj.dimensions.z:.0f} mm tall")

    if a.hollow > 0:
        hollow(obj, a.hollow)

    parts, step = split(obj, a.bed)
    os.makedirs(a.outdir, exist_ok=True)

    print("\n--- bust ---")
    total_g = 0.0
    for part in parts:
        bpy.context.view_layer.objects.active = part
        decimate(part, a.tris)
        path = os.path.join(a.outdir, f"{part.name}.stl")
        export(part, path)
        vol, area, closed, tris = stats(part)
        grams = filament_grams(vol, area)
        total_g += grams
        d = part.dimensions
        print(f"{part.name:14s} {d.x:6.1f} x {d.y:6.1f} x {d.z:6.1f} mm  "
              f"{tris:6d} tris  ~{grams:5.0f} g PLA  manifold={closed}")

    if len(parts) > 1:
        dowel = make_dowel(PIN_D, 14.0)
        export(dowel, os.path.join(a.outdir, "dowel.stl"))
        print(f"{'dowel':14s} Ø{PIN_D} x 14 mm  -- print {2 * (len(parts)-1)}, "
              f"holes are Ø{PIN_D + 2*PIN_CLEAR}")
        print(f"split into {len(parts)} sections of {step:.0f} mm")
    print(f"{'total':14s} ~{total_g:.0f} g PLA at 3 walls / 10% infill "
          f"(estimate -- trust the slicer)")


if __name__ == "__main__":
    main()
