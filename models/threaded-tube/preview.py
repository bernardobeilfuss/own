"""
Render a preview PNG of the tube: exploded 3D view plus a cut-away that
shows the threads actually interlocking.

    python3 preview.py [-o preview.png]
"""

import argparse
import math
import os

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import generate as g
from validate import to_mesh

BG, INK, ACCENT = "#14161a", "#e9edf2", "#f0803c"
SEATED_Z = g.BODY_H - g.CAP_CAVITY
BEST_PHASE = 102.0   # phase found by validate.py's screw test


def shade(mesh, base, light=(0.4, 0.5, 0.75)):
    tris = mesh.vertices[mesh.faces]
    n = mesh.face_normals
    lit = np.clip(n @ np.array(light) / np.linalg.norm(light), 0, 1)
    c = np.array(matplotlib.colors.to_rgb(base))
    colors = c * (0.32 + 0.68 * lit)[:, None]
    return Poly3DCollection(tris, facecolors=np.clip(colors, 0, 1), linewidths=0)


def seated_cap(cap):
    c = cap.copy()
    c.apply_transform(
        trimesh.transformations.rotation_matrix(math.radians(BEST_PHASE), (0, 0, 1))
    )
    c.apply_translation((0, 0, SEATED_Z))
    return c


def view_3d(ax, body, cap):
    cap = cap.copy()
    cap.apply_translation((0, 0, SEATED_Z + 16))   # exploded
    ax.add_collection3d(shade(body, "#7f8b99"))
    ax.add_collection3d(shade(cap, ACCENT))
    ax.set_xlim(-20, 20)
    ax.set_ylim(-20, 20)
    ax.set_zlim(0, 82)
    ax.set_box_aspect((1, 1, 2.05))
    ax.set_axis_off()
    ax.view_init(elev=14, azim=35)
    ax.set_title("exploded", color=INK, fontsize=9, pad=0)


def view_section(ax, body, cap, window=None, title="section, screwed shut"):
    """Cut the assembly at y = 0 and draw the real X-Z outline.

    Path3D.to_2D() reprojects onto its own frame, which scrambles the axes
    here; the discrete polylines are already in world coordinates.
    """
    for mesh, color in ((body, "#7f8b99"), (seated_cap(cap), ACCENT)):
        sec = mesh.section(plane_origin=(0, 0, 0), plane_normal=(0, 1, 0))
        for loop in sec.discrete:
            ax.fill(loop[:, 0], loop[:, 2], facecolor=color,
                    edgecolor=INK, linewidth=0.5, alpha=0.95)

    if window:
        ax.set_xlim(*window[0])
        ax.set_ylim(*window[1])
    else:
        ax.set_xlim(-14, 14)
        ax.set_ylim(-2, 64)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(title, color=INK, fontsize=9, pad=2)


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("-o", "--out", default=os.path.join(here, "preview.png"))
    args = ap.parse_args()

    body, cap = to_mesh(g.body().val()), to_mesh(g.cap().val())

    fig = plt.figure(figsize=(9.5, 5.4), facecolor=BG)
    gs = fig.add_gridspec(1, 3, width_ratios=(1.15, 0.8, 1.05), wspace=0.02)
    view_3d(fig.add_subplot(gs[0], projection="3d", facecolor=BG), body, cap)
    view_section(fig.add_subplot(gs[1], facecolor=BG), body, cap)
    view_section(
        fig.add_subplot(gs[2], facecolor=BG), body, cap,
        window=((6.5, 13.5), (44.5, 59.5)),
        title=f"thread detail  ·  Ø{g.THREAD_MAJOR:.0f} x {g.PITCH}  ·  "
              f"{g.RAD_CLEAR} mm/flank",
    )
    fig.suptitle(
        f"threaded tube  ·  {g.ASSEMBLED_H:.0f} mm assembled  ·  "
        f"{math.pi * (g.BORE/2)**2 * (g.BODY_H - g.BOTTOM) / 1000:.1f} mL  ·  "
        f"parametric CAD, mesh-validated",
        color=INK, fontsize=12, y=0.965,
    )
    fig.savefig(args.out, dpi=170, facecolor=BG, bbox_inches="tight")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
