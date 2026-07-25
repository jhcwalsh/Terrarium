"""Albourne derived cashflow measures, groups A-E (albourne-derived-measures-spec.md).

A — lifecycle profiles by fund age (mean, p25, p75).
B — quarterly aggregate calendar rate series.
C — age x calendar rate matrices with fund counts.
D — vintage-year TVPI/DPI/IRR quartiles with fund counts.
E — episode cuts (flagged extracts of B); non-contiguous by design (no gap check).
"""

from __future__ import annotations

from ah.data.schemas.base import ColumnSpec, IntakeSchema

CF_A_LIFECYCLE = IntakeSchema(
    name="albourne_cf_A_lifecycle",
    source="albourne",
    columns=[
        ColumnSpec("strategy", dtype="str"),
        ColumnSpec("fund_age", dtype="int", min=1, max=15),
        ColumnSpec("metric", dtype="str"),  # call_rate | dist_rate | nav_pct | dpi | ...
        ColumnSpec("mean", dtype="float"),
        ColumnSpec("p25", dtype="float"),
        ColumnSpec("p75", dtype="float"),
    ],
    notes="age-indexed lifecycle curves with dispersion (the empirical 'bow').",
)

CF_B_CALENDAR = IntakeSchema(
    name="albourne_cf_B_calendar_rates",
    source="albourne",
    columns=[
        ColumnSpec("period", dtype="period"),
        ColumnSpec("strategy", dtype="str"),
        ColumnSpec("agg_call_rate", dtype="float", min=0.0, max=2.0),
        ColumnSpec("agg_dist_rate", dtype="float", min=0.0, max=2.0),
        ColumnSpec("net_cf_yield", dtype="float", min=-2.0, max=2.0),
    ],
    period_col="period",
    frequency="Q",
    group_col="strategy",
    notes="market-linkage panel: quarterly aggregate call/distribution rates.",
)

CF_C_AGE_CALENDAR = IntakeSchema(
    name="albourne_cf_C_age_calendar",
    source="albourne",
    columns=[
        ColumnSpec("strategy", dtype="str"),
        ColumnSpec("fund_age", dtype="int", min=1, max=15),
        ColumnSpec("period", dtype="period"),
        ColumnSpec("call_rate", dtype="float", min=0.0, max=2.0),
        ColumnSpec("dist_rate", dtype="float", min=0.0, max=2.0),
        ColumnSpec("fund_count", dtype="int", min=0),
    ],
    notes="Lexis-style age x calendar rate surface with cell fund counts.",
)

CF_D_VINTAGE = IntakeSchema(
    name="albourne_cf_D_vintage",
    source="albourne",
    columns=[
        ColumnSpec("strategy", dtype="str"),
        ColumnSpec("vintage_year", dtype="int", min=1970, max=2100),
        ColumnSpec("tvpi", dtype="float", min=0.0, max=10.0),
        ColumnSpec("dpi", dtype="float", min=0.0, max=10.0),
        ColumnSpec("irr", dtype="float", min=-1.0, max=5.0),
        ColumnSpec("quartile", dtype="int", min=1, max=4),
        ColumnSpec("fund_count", dtype="int", min=0),
    ],
    notes="vintage-year quartiles and dispersion.",
)

CF_E_EPISODES = IntakeSchema(
    name="albourne_cf_E_episodes",
    source="albourne",
    columns=[
        ColumnSpec("period", dtype="period"),
        ColumnSpec("strategy", dtype="str"),
        ColumnSpec("call_rate", dtype="float", min=0.0, max=2.0),
        ColumnSpec("dist_rate", dtype="float", min=0.0, max=2.0),
        ColumnSpec("episode", dtype="str"),
    ],
    period_col="period",
    frequency=None,  # episode cuts are intentionally non-contiguous -> no gap check
    group_col="strategy",
    notes="flagged episode extracts of group B (2008-10, 2020, 2022-23).",
)

ALL = [CF_A_LIFECYCLE, CF_B_CALENDAR, CF_C_AGE_CALENDAR, CF_D_VINTAGE, CF_E_EPISODES]
