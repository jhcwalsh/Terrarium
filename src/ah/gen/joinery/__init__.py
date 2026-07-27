"""WP2.7 Layer 4 — waypoints, bridging, reconciliation, support monitoring.

DN-1.1 §II.5 is normative: L1/L2 set the year-by-year skeleton of each decade
(waypoints), a block generator fills in the monthly path between them (bridge),
Denton benchmarking makes the books balance exactly (reconcile), and the
conditioning-support monitor instruments the interface conditional generators
fail quietly on (support). ``assemble`` runs the 7-step algorithm end to end.

Layering: this package imports L1 (:mod:`ah.gen.climate.simulate`), L2
(:mod:`ah.gen.regimes.semimarkov`) and the bootstrap stand-in block source
(:mod:`ah.gen.bootstrap`), and never anything under :mod:`ah.eval` — the
acceptance-filter statistics are local numpy implementations, deliberately not
the sealed estimators (see ``assemble``'s module docstring).
"""

from ah.gen.joinery.assemble import GENERATOR_ID, JoineryConfig, assemble_decades
from ah.gen.joinery.bridge import (
    C_B_COMPONENTS,
    C_B_DIM,
    BlockConditioning,
    BlockSampler,
    BootstrapBlockSampler,
)
from ah.gen.joinery.reconcile import ReconcileConfig, reconcile_decade
from ah.gen.joinery.support import SupportReference, build_support_reference, decade_support
from ah.gen.joinery.waypoints import (
    DecadeWaypoints,
    JoineryError,
    SourceStats,
    build_waypoints,
    monthly_targets,
    source_stats,
)

__all__ = [
    "C_B_COMPONENTS",
    "C_B_DIM",
    "GENERATOR_ID",
    "BlockConditioning",
    "BlockSampler",
    "BootstrapBlockSampler",
    "DecadeWaypoints",
    "JoineryConfig",
    "JoineryError",
    "ReconcileConfig",
    "SourceStats",
    "SupportReference",
    "assemble_decades",
    "build_support_reference",
    "build_waypoints",
    "decade_support",
    "monthly_targets",
    "reconcile_decade",
    "source_stats",
]
