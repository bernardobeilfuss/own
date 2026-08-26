#!/usr/bin/env bash
# Set up a machine to prepare a memorial bust for printing.
#
#   ./setup.sh              core only -- enough to run prepare_bust.py
#   ./setup.sh --with-recon core plus the face-reconstruction stack
#
# The core half is self-contained and will work. The reconstruction half
# needs model weights that are license-gated; this script tells you which
# and where, it does not accept anyone's licence on your behalf.

set -euo pipefail
RECON=0
[[ "${1:-}" == "--with-recon" ]] && RECON=1

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }

say "1. Blender"
if command -v blender >/dev/null 2>&1; then
    echo "   found: $(blender --version 2>/dev/null | head -1)"
else
    warn "not installed."
    case "$(uname -s)" in
        Linux)  echo "   sudo apt install blender    # or: sudo snap install blender --classic" ;;
        Darwin) echo "   brew install --cask blender" ;;
        *)      echo "   https://www.blender.org/download/" ;;
    esac
    echo "   4.0 or newer. Re-run this script afterwards."
fi

say "2. Python environment"
PY=$(command -v python3.11 || command -v python3.10 || command -v python3)
echo "   using $PY ($($PY --version))"
$PY -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip

say "3. Core packages"
pip install --quiet numpy trimesh manifold3d shapely networkx matplotlib
echo "   trimesh, manifold3d (booleans), matplotlib (previews)"

if [[ $RECON -eq 1 ]]; then
    say "4. Reconstruction packages"
    pip install --quiet mediapipe opencv-python-headless
    echo "   mediapipe (3D face landmarks), opencv"
    echo "   torch is NOT installed here -- pick the build that matches your"
    echo "   GPU at https://pytorch.org/get-started/locally/ , since the CPU"
    echo "   wheel and the CUDA wheel are different downloads."

    say "5. Model weights you have to fetch yourself"
    cat <<'NOTE'
   FLAME (the face model most single-image pipelines are built on)
     https://flame.is.tue.mpg.de/  -- register, accept the licence, download
     Non-commercial research licence. Approval is not always instant, so
     start this before you need it.

   DECA / EMOCA / HRN (the network that fits FLAME to a photo)
     Each ships its own weights; check the repo you settle on.

   Commercial alternative, no licence dance: Tripo, Meshy, Luma. Upload the
   photo, download a mesh, hand it to prepare_bust.py. Lower ceiling on
   fidelity, far less setup.
NOTE
fi

say "Done"
echo "   source .venv/bin/activate"
echo "   blender --background --python prepare_bust.py -- --input head.obj \\"
echo "       --name \"...\" --dates \"...\" --height 150"
