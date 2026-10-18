#!/usr/bin/env bash
# Download the released trajectories from Zenodo, verify them, and unpack them
# into data/simulations/<run>/results.json. Run from the repository root:
#   bash data/download.sh            # all twelve archives (about 240 MB)
#   bash data/download.sh grid-sas grid-mas   # a subset
# Then: bash setup.sh   (links each run into tau2-bench/data/simulations/)
set -euo pipefail

ZENODO_RECORD="${ZENODO_RECORD:-TODO_ZENODO_RECORD_ID}"   # numeric record id of the deposit
BASE="https://zenodo.org/records/${ZENODO_RECORD}/files"
cd "$(dirname "$0")"
ALL=(grid-sas grid-mas r1 r2 uncapped rc25 s2 local-4b gate-and-pilots smokes not-in-paper collaborator)
GROUPS=("$@"); [ ${#GROUPS[@]} -eq 0 ] && GROUPS=("${ALL[@]}")

if [ "$ZENODO_RECORD" = "TODO_ZENODO_RECORD_ID" ]; then
  echo "Set ZENODO_RECORD (the Zenodo record id) at the top of this script or in the environment." >&2
  exit 1
fi
command -v sha256sum >/dev/null || sha256sum() { shasum -a 256 "$@"; }

mkdir -p archives simulations
for g in "${GROUPS[@]}"; do
  f="archives/${g}.tar.gz"
  if [ ! -f "$f" ]; then
    echo "==> downloading ${g}.tar.gz"
    curl -L --fail --retry 3 -o "$f" "${BASE}/${g}.tar.gz?download=1"
  fi
  want=$(grep " ${g}.tar.gz\$" SHA256SUMS | cut -d' ' -f1)
  have=$(sha256sum "$f" | cut -d' ' -f1)
  if [ "$want" != "$have" ]; then echo "checksum mismatch for $f" >&2; exit 1; fi
  echo "==> unpacking ${g}.tar.gz"
  if [ "$g" = collaborator ]; then
    tar xzf "$f" -C simulations --strip-components=1   # archive root is collaborator/<run>/
  else
    tar xzf "$f" -C simulations
  fi
done
echo "done: $(ls simulations | wc -l | tr -d ' ') run folders under data/simulations/"
