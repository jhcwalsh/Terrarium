"""WP2.8/2.9 Layer 3 — the conditional block generators (DN-1.1 §II.4).

``data.py`` builds the training set of overlapping L-month blocks with their
frozen cb-v1 conditioning vectors (built by :mod:`ah.gen.joinery.bridge`'s own
machinery — one code path for training and generation). ``constraints.py`` maps
factor units to unconstrained coordinates so hard floors are structurally
impossible to violate. ``losses.py`` holds the generative-objective interface
(EDM denoising score matching here; WP2.9's velocity matching behind the same
protocol) and the D4 tail-elicitability auxiliary in the WP2.2c-corrected
direction. ``diffusion.py`` is the EDM-style sampler implementing the joinery
``BlockSampler`` protocol; ``train.py``/``tuning.py`` are deterministic training
and the sealed forking-paths tuning record (pre-registration.yaml
``tuning_protocol``, binding).

No module in this package imports ``ah.eval`` (AST-enforced): every statistic
that feeds a training decision is a local implementation.
"""
