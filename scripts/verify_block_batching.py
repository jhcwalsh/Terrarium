"""WP2.8b evidence — assemble the SAME ensemble at several block-batch widths.

Runs :func:`ah.gen.joinery.assemble.assemble_decades` end to end with the REAL
trained L3a checkpoint (0.94M parameters) over SYNTHETIC L1/L2 artifacts and a
synthetic 12-factor source, so it needs no catalog and no network. It prints, per
width, the wall clock and the SHA-256 of the emitted ``paths`` array, plus the
element-wise divergence against the width-1 (legacy, per-block) reference.

Width 1 must reproduce the pre-batching code BIT FOR BIT; wider batches cannot,
because the float32 GEMM this network is built from is not batch-size invariant
(measured: a row's denoiser output changes by ~1.5e-7 relative between batch 1
and batch 2 on both CPU and CUDA). This script is how that claim is evidenced.

    uv run python scripts/verify_block_batching.py --widths 1 8 64 --decades 20
    uv run python scripts/verify_block_batching.py --device cuda --widths 1024
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "tests"))

from ah.gen.blocks import diffusion as df  # noqa: E402
from ah.gen.joinery import bridge  # noqa: E402
from ah.gen.joinery.assemble import JoineryConfig, assemble_decades  # noqa: E402
from joinery_common import (  # noqa: E402
    make_climate_artifact,
    make_regimes_artifact,
    make_source,
)


def _digest(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--widths", type=int, nargs="+", default=[1, 8, 64])
    p.add_argument("--decades", type=int, default=20)
    p.add_argument("--months", type=int, default=120)
    p.add_argument("--seed", type=int, default=20260727)
    p.add_argument("--device", default="cpu")
    p.add_argument("--threads", type=int, default=1)
    p.add_argument("--filter", action="store_true", help="run with the acceptance filter on")
    p.add_argument("--out", type=Path, default=None, help="write the width-1 paths here (.npy)")
    p.add_argument("--against", type=Path, default=None, help="compare width-1 to this .npy")
    args = p.parse_args()

    if args.device.startswith("cuda"):
        # deterministic cuBLAS needs a fixed workspace; set before torch loads
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

    import torch

    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)

    scratch = _REPO_ROOT / ".verify-block-batching"
    climate = make_climate_artifact(scratch / "clim", t_months=480, state_noise=0.05)
    regimes = make_regimes_artifact(scratch / "reg")
    source = make_source(n_rows=240)

    model, std, meta = df.load_checkpoint(df.DEFAULT_CHECKPOINT)
    print(f"checkpoint {meta['checkpoint_hash'][:16]}  device={args.device}")
    print(f"{args.decades} decades x {args.months} months, seed {args.seed}, filter={args.filter}")

    reference: np.ndarray | None = None
    if args.against is not None:
        reference = np.load(args.against)

    print(f"\n{'width':>6} {'wall s':>9} {'sha256(paths)':>18}  divergence vs width 1")
    for width in args.widths:
        sampler = df.DiffusionBlockSampler(
            model,
            std,
            tuple(source.factor_names),
            trained_fingerprint=bridge.contract_fingerprint(),
            device=args.device,
            block_batch=width,
        )
        t0 = time.perf_counter()
        ens = assemble_decades(
            climate=climate,
            regimes_artifact=regimes,
            source=source,
            n_decades=args.decades,
            seed=args.seed,
            months=args.months,
            sampler=sampler,
            config=JoineryConfig(acceptance_filter=args.filter),
        )
        wall = time.perf_counter() - t0
        line = f"{width:>6} {wall:>9.1f} {_digest(ens.paths)[:16]:>18}"
        if reference is None:
            reference = ens.paths.copy()
            line += "  (reference)"
            if args.out is not None:
                np.save(args.out, ens.paths)
                line += f" -> {args.out.name}"
        else:
            d = np.abs(ens.paths - reference)
            rel = d / np.maximum(np.abs(reference), 1e-300)
            line += (
                f"  exact={bool(np.array_equal(ens.paths, reference))}"
                f"  max|d|={float(d.max()):.3e}  max rel={float(rel.max()):.3e}"
            )
            print(line)
            # Per factor, scaled by that factor's own cross-ensemble spread. A raw
            # max-relative figure is dominated by cells whose reference value is
            # near zero (monthly factor returns sit at ~1e-3), which says nothing
            # about whether the ensembles agree.
            print(f"{'':>6} {'factor':>16} {'max|d|':>11} {'max|d|/sd':>11} {'sd':>11}")
            for j, name in enumerate(ens.factor_names):
                sd = float(np.std(reference[..., j]))
                dj = float(d[..., j].max())
                print(f"{'':>6} {name:>16} {dj:>11.3e} {dj / max(sd, 1e-300):>11.3e} {sd:>11.3e}")
            continue
        print(line)


if __name__ == "__main__":
    main()
