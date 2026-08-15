"""Generator layer (Step 2): benchmark + the four-layer hierarchical generator.

pandas/numpy/torch permitted here (like ``ah.data``, unlike ``ah.core``). No module
in this package may import ``ah.eval.g2`` — that is where the holdout token is minted
(enforced by the import-graph test). The stated rule is wider than the enforced one:
no module here imports ``ah.eval`` at all (``tests/test_bootstrap.py`` proves it).

``bootstrap`` is imported for its side effect — it registers ``bootstrap-v1`` in
:mod:`ah.gen.registry` (WP2.4). Registration has to happen on *some* import, and this
is the one every consumer already performs: ``ah.eval.metrics.conditional`` resolves the
generator under test by id at battery-run time, so a benchmark that registered only when
someone remembered to import it would be silently absent from its own conditional suite.
The import is cheap — the catalog is read lazily, on first ``bootstrap_v1_factory()``.
"""

from ah.gen import bootstrap as bootstrap

# imported for its side effect — re-registers `bootstrap-stratified` as the
# x_stress dispatcher; must import after bootstrap so this registration wins
from ah.gen import stress as stress
