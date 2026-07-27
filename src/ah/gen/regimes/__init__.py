"""WP2.6 Layer 2 -- the semi-Markov regime skeleton (DN-1.1 SS II.3).

``semimarkov``: config (YAML -> pydantic, hashed), the hash-verified posterior
artifact, and numpy-only seeded simulation -- the fitted skeleton conditioned on
Layer-1 slow states, plus the three WorldSpec regime modes (sequence exact,
transition_matrix honoured verbatim, unconditional = historical frequencies) and
the cycle term c_t in [-1, +1] that fulfils WP2.5's contract.

``fit``: label/covariate assembly through the sanctioned split surface
(train+validation only), the numpyro model (NegBin sojourns + multinomial-logit
transitions, both logit-linked to z(s)), NUTS, diagnostics, the deterministic
posterior artifact, the acceptance-band evidence (block-bootstrap label bands vs
simulated durations/frequencies), and the regime_ruleset_v1b sensitivity refit.

No module here may import ``ah.eval`` (leakage guard; import-graph test).
"""
