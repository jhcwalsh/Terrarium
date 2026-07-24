"""The G2 decision rule + the sanctioned holdout-token mint (STEP2 §WP2.1, §WP2.11).

This module is deliberately the *only* place a :class:`~ah.splits.FinalEvaluationToken`
is created: the touch-once holdout is reachable only from here, and the import-graph
test proves no training/generator module imports this module. The multi-seed G2
decision rule itself is implemented in WP2.11; here we establish the token boundary.
"""

from __future__ import annotations

from ah.splits import FinalEvaluationToken


def final_evaluation_token() -> FinalEvaluationToken:
    """Mint the one-time holdout access token. Call site is WP2.11's G2 evaluation only."""
    return FinalEvaluationToken(purpose="final-evaluation")
