"""WP2.5 Layer 1 -- the climate model (DN-1.1 SS II.2).

``model``: numpyro/JAX state-space model (marginalized Kalman likelihood, FFBS).
``fit``: data assembly through the sanctioned split surface, NUTS, diagnostics,
the deterministic posterior artifact, and the generated climate-fit-report.
``simulate``: numpy-only decade simulation from a fitted artifact -- (theta, s0)
drawn per decade, so parameter uncertainty is inside the ensemble by construction.

No module here may import ``ah.eval`` (leakage guard; import-graph test).
"""
