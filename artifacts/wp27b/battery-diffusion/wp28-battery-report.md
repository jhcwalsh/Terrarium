# WP2.8 hier-diffusion-v1 battery + joinery diagnostics

- system: hier-diffusion-v1 (L1+L2+L4, trained 3a blocks)
- checkpoint: f0c79f000be659c8b443afba02a251ab8925d995fdebcf8e6e82195e8dd70c5a
- vintage 2026-07-26.1; n_paths 1024; months 120; seed 20260727; criterion_bearing True
- battery verdict: unfiltered PASS (0/5 enforce failures); filtered 0 failures

### Reconciliation shrinkage vs the WP2.7 bootstrap baseline

- policy_rate (additive): p50 1.45987, p90 2.54666, max 8.14954, flagged 848 (wp2.7 baseline p50 2.86737, p90 5.10771)
- cpi (proportional_via_log): p50 0.09521, p90 0.22842, max 0.57457, flagged 677 (wp2.7 baseline p50 0.16745, p90 0.56993)
- equity_mkt (additive_log_returns): p50 0.01688, p90 0.02592, max 0.04750, flagged 107 (wp2.7 baseline p50 0.01110, p90 0.01838)
- ig_spread (additive_band): p50 0.18343, p90 0.60017, max 1.22678, flagged 0 (wp2.7 baseline p50 0.02425, p90 0.08216)

### Support / off-support
- extrapolation share mean 0.8742 (wp2.7 baseline 0.8799)
- decades flagged off-support: 1006 (baseline 1009)
- regime TV mean 0.3357 (baseline 0.3357)
- sampler fallbacks: {}

### Waypoint tolerance
- {'n_decades_ok': 1024, 'all_ok': True, 'floor_clamped_cells': 23868, 'n_floor_bound_years': 4243}
