"""The portfolio engine (WP3.7) — the cash waterfall, spending, forced sales.

Liquidity-spine §7-§8 as a quarterly orchestrator over WP3.1's state objects:

1. Cash receives distributions and evergreen income
2. Cash pays capital calls
3. Cash pays spending — a fixed rate on the trailing twelve-quarter average of
   **REPORTED** total value (§7 verbatim: endowments spend off the values in
   their accounts, which contain smoothed private marks — so spending holds up
   in absolute terms exactly when liquid assets are scarcest; one line of code,
   and without it the episode is materially milder than the real thing)
4. If cash < 0 → **forced sale**: liquid sleeves pro-rata, then a forced
   secondary sale of cohort NAV at the policy haircut — every event logged with
   period, amount, cause, and sleeves sold (the headline output, never a
   footnote)

Plus private-weight breach detection against the policy range, on both bases.
Deterministic: the engine consumes per-quarter inputs (sleeve returns, market
states) and applies rules; it draws nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from ah.port.portfolio import Portfolio


class EngineError(ValueError):
    """A policy or step input the engine refuses to run."""


@dataclass(frozen=True)
class Policy:
    """The institution's standing policy (register kind C — chosen, stated)."""

    spending_rate_annual: float = 0.045
    spending_trailing_quarters: int = 12
    secondary_haircut: float = 0.19  # 0.81 NAV — the 2022-H2 public anchor
    private_weight_range: tuple[float, float] = (0.15, 0.40)

    def __post_init__(self) -> None:
        if not 0.0 <= self.spending_rate_annual <= 0.20:
            raise EngineError("spending rate out of range")
        if not 0.0 <= self.secondary_haircut < 1.0:
            raise EngineError("secondary haircut must be in [0, 1)")
        lo, hi = self.private_weight_range
        if not 0.0 <= lo < hi <= 1.0:
            raise EngineError("private weight range must be 0 <= lo < hi <= 1")


@dataclass
class QuarterReport:
    period: int
    distributions_received: float
    calls_paid: float
    spending_paid: float
    forced_sale_total: float
    cash_end: float
    private_weight_true: float
    private_weight_reported: float
    breach_true: bool
    breach_reported: bool
    coverage_true: float
    coverage_liquid: float


class PortfolioEngine:
    """Runs the waterfall; the caller steps the sleeves and hands in the flows."""

    def __init__(self, portfolio: Portfolio, policy: Policy | None = None) -> None:
        self.portfolio = portfolio
        self.policy = policy or Policy()
        self._reported_history: list[float] = []
        self._period = 0

    def run_quarter(
        self,
        *,
        distributions: float,
        calls: float,
        evergreen_income: float = 0.0,
    ) -> QuarterReport:
        """One quarter of §8's waterfall, in order, after the caller has applied
        returns and stepped every sleeve."""
        if distributions < 0.0 or calls < 0.0 or evergreen_income < 0.0:
            raise EngineError("flows must be non-negative")
        p = self.portfolio
        policy = self.policy
        self._period += 1

        # 1. cash receives
        p.cash += distributions + evergreen_income
        # 2. cash pays calls
        p.cash -= calls
        # 3. spending, off the trailing average of REPORTED value (§7)
        self._reported_history.append(p.nav_reported())
        window = self._reported_history[-policy.spending_trailing_quarters :]
        spending = (policy.spending_rate_annual / 4.0) * (sum(window) / len(window))
        p.cash -= spending

        # 4. shortfall resolution
        forced_total = 0.0
        if p.cash < 0.0:
            shortfall = -p.cash
            # 4a. liquid sleeves pro-rata
            liquid_total = sum(liq.value for liq in p.liquid.values())
            sold_liquid = min(shortfall, liquid_total)
            if sold_liquid > 0.0 and liquid_total > 0.0:
                sleeves_sold = []
                for key, liq in p.liquid.items():
                    share = liq.value / liquid_total
                    liq.sell(sold_liquid * share)
                    sleeves_sold.append(key)
                p.cash += sold_liquid
                shortfall -= sold_liquid
                forced_total += sold_liquid
                p.forced_sales.append(
                    {
                        "period": self._period,
                        "amount": sold_liquid,
                        "cause": "cash shortfall after calls and spending",
                        "kind": "liquid_pro_rata",
                        "sleeves_sold": sleeves_sold,
                    }
                )
            # 4b. forced secondary at the policy haircut
            if shortfall > 1e-12:
                nav_available = sum(c.nav_true for c in p.cohorts.values())
                # selling S of NAV raises S*(1-haircut) of cash
                nav_to_sell = min(nav_available, shortfall / (1.0 - policy.secondary_haircut))
                raised = nav_to_sell * (1.0 - policy.secondary_haircut)
                sleeves_sold = []
                if nav_available > 0.0 and nav_to_sell > 0.0:
                    for key, cohort in p.cohorts.items():
                        share = cohort.nav_true / nav_available
                        cohort.nav_true -= nav_to_sell * share
                        cohort.nav_reported = max(0.0, cohort.nav_reported - nav_to_sell * share)
                        sleeves_sold.append(key)
                    p.cash += raised
                    shortfall -= raised
                    forced_total += raised
                    p.forced_sales.append(
                        {
                            "period": self._period,
                            "amount": raised,
                            "nav_sold": nav_to_sell,
                            "haircut": policy.secondary_haircut,
                            "cause": "liquid sleeves exhausted; forced secondary",
                            "kind": "forced_secondary",
                            "sleeves_sold": sleeves_sold,
                        }
                    )

        lo, hi = policy.private_weight_range
        w_true = p.private_weight_true()
        w_rep = p.private_weight_reported()
        return QuarterReport(
            period=self._period,
            distributions_received=distributions + evergreen_income,
            calls_paid=calls,
            spending_paid=spending,
            forced_sale_total=forced_total,
            cash_end=p.cash,
            private_weight_true=w_true,
            private_weight_reported=w_rep,
            breach_true=not lo <= w_true <= hi,
            breach_reported=not lo <= w_rep <= hi,
            coverage_true=p.coverage_true(),
            coverage_liquid=p.coverage_liquid(),
        )
