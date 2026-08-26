"""
Render the prepared bust: whole, and split with its dowel holes showing.

    python3 preview_bust.py --whole out/bust.stl --parts out3/bust-1of2.stl ...
"""

import argparse

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

BG, INK = "#14161a", "#e9edf2"
CLAY = ["#9aa7b4", "#f0803c", "#6f9ea8"]


def shade(ax, mesh, base, light=(0.35, -0.6, 0.7)):
    n = mesh.face_normals
    lit = np.clip(n @ (np.array(light) / np.linalg.norm(light)), 0, 1)
    c = np.array(matplotlib.colors.to_rgb(base))
    ax.add_collection3d(Poly3DCollection(
        mesh.vertices[mesh.faces],
        facecolors=np.clip(c * (0.30 + 0.70 * lit)[:, None], 0, 1),
        linewidths=0))


def frame(ax, height, title):
    r = height * 0.42
    ax.set_xlim(-r, r)
    ax.set_ylim(-r, r)
    ax.set_zlim(0, height)
    ax.set_box_aspect((1, 1, height / (2 * r)))
    ax.set_axis_off()
    ax.view_init(elev=8, azim=-72)
    ax.set_title(title, color=INK, fontsize=9, pad=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--whole", required=True)
    ap.add_argument("--parts", nargs="+", required=True)
    ap.add_argument("-o", "--out", default="preview.png")
    a = ap.parse_args()

    whole = trimesh.load(a.whole)
    parts = [trimesh.load(p) for p in a.parts]

    fig = plt.figure(figsize=(8.6, 5.0), facecolor=BG)
    ax1 = fig.add_subplot(1, 2, 1, projection="3d", facecolor=BG)
    shade(ax1, whole, CLAY[0])
    frame(ax1, whole.extents[2], f"one piece  ·  {whole.extents[2]:.0f} mm tall")

    ax2 = fig.add_subplot(1, 2, 2, projection="3d", facecolor=BG)
    z, gap = 0.0, 14.0
    for i, p in enumerate(parts):
        m = p.copy()
        m.apply_translation((0, 0, z - m.bounds[0][2]))
        shade(ax2, m, CLAY[i % len(CLAY)])
        z += m.extents[2] + gap
    frame(ax2, z, f"split for the bed  ·  {len(parts)} sections + dowels")

    fig.suptitle("memorial bust  ·  print preparation, stand-in geometry",
                 color=INK, fontsize=11, y=0.97)
    fig.savefig(a.out, dpi=165, facecolor=BG, bbox_inches="tight")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
