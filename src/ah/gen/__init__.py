"""Generator layer (Step 2): benchmark + the four-layer hierarchical generator.

pandas/numpy/torch permitted here (like ``ah.data``, unlike ``ah.core``). No module
in this package may import ``ah.eval.g2`` — that is where the holdout token is minted
(enforced by the import-graph test).
"""
