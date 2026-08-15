/* ==================================================================
 *  cioView.ts — CIO dashboard view-model contract
 *  Terrarium · v0.3 · companion to DN-8
 *
 *  The dashboard renders one CioView and computes nothing else. If a
 *  number appears on screen it appears in this file, and the engine
 *  is responsible for it.
 *
 *  CONVENTIONS — enforced by validateCioView(), not by TypeScript
 *  ------------------------------------------------------------------
 *  Percent    numbers in percentage points. 26.1 means 26.1%.
 *             EXCEPT ratio fields explicitly typed Ratio (0.51).
 *  Money      numbers in meta.unitLabel. Default $m.
 *  Signs      calls, distributions, payout, income are POSITIVE
 *             MAGNITUDES. The renderer applies direction.
 *             net = distributions − calls  (may be negative)
 *             forecast12m.net = distributions + income − calls − payout
 *  Missing    any period the run has not reached is null. Never 0,
 *             never omitted from a fixed-length array. The renderer
 *             prints an em dash for null and would print "+0.0" for 0.
 *  Order      arrays are ordered as displayed. The renderer does not
 *             sort. allocation.classes must be grouped by goal in the
 *             order allocation.goals declares.
 *  Purity     buildCioView must be a pure function of the RunRecord.
 *             Same RunRecord + same plane + same asOf ⇒ same payload,
 *             byte for byte. This is what keeps the screen inside the
 *             replay guarantee.
 * ================================================================== */

export type Plane = "reported" | "true";
/**
 * Band status for a weight against its target.
 *   ok      inside the band, not close to it
 *   watch   inside the band but within the alert threshold of the edge (amber)
 *   breach  outside the band (red)
 */
export type AlertLevel = "ok" | "watch" | "breach";
export type Ratio = number;    // 0.51 means 51%
export type Percent = number;  // 26.1 means 26.1%
export type Money = number;    // in meta.unitLabel
export type Nullable<T> = T | null;

/* ------------------------------------------------------------------ */

export interface CioView {
  meta: Meta;
  plan: Plan;
  allocation: Allocation;
  performance: Performance;
  liquidity: Liquidity;
  privateCashflows: PrivateCashflows;
  markets?: Markets;
}

export interface Meta {
  /** RunRecord id. Rendered in the footer; every screenshot is traceable. */
  runId: string;
  seed: string;
  worldTitle: string;
  worldVersion: string;
  /** public-0.1 | panel-1.0 — disclosed on screen, not optional. */
  linkageVersion: string;
  decisionAlphaVersion: string;
  /** Display label for the cursor, e.g. "Y4 Q3". */
  asOfLabel: string;
  /** Machine cursor: months elapsed since world start. */
  asOfMonth: number;
  regime?: string;
  /** Which plane THIS payload is on. */
  plane: Plane;
  /** Planes the host may request. Public tier ships ["reported"] only. */
  planesAvailable: Plane[];
  unitLabel: string;   // "$m"
  unitSuffix: string;  // "m"
  currency: string;    // "USD"
  watermark: string;
  disclaimer: string;
}

/* ---- 1. Plan growth ---------------------------------------------- */

export interface Plan {
  totalValue: Money;
  growthPct: Nullable<Percent>;
  /** Change attributable to markets, i.e. net of contributions and payouts. */
  netOfFlows: Nullable<Money>;
  windowLabel: string;
  preRunLabel?: string;
  worldStartLabel?: string;
  history: {
    /** Monthly, oldest first. Length sets the window; ticks are drawn every 12. */
    values: number[];
    /**
     * Index into values at which the WORLD's own history begins (i.e. the
     * inherited decade, if any, occupies indices before this one).
     * Everything before it is drawn hatched and dashed. Set 0 if the world
     * supplies no pre-history — see DN-8 §O-1, which is the governing open
     * item.
     */
    worldStartIndex: number;
  };
}

/* ---- 2. Allocation ----------------------------------------------- */

export interface Goal {
  id: string;      // growth | real | income | diversifier — colours are keyed on these
  label: string;
  /** Deviation beyond which the goal total is a breach. Acts as the goal's band. */
  tolerancePct?: Percent;
  /** Engine-supplied status. Wins over the fallback rule if present. */
  alert?: AlertLevel;
}

/**
 * Alert policy for weights against target.
 *
 * The renderer can determine a BREACH without a parameter: |dev| > band.
 * It cannot determine a WATCH without a threshold, and a threshold is a
 * parameter — so the renderer carries no default. If watchFraction is
 * absent, amber never fires and only breaches are flagged. Supply it,
 * or supply an explicit `alert` per row.
 *
 * watchFraction 0.75 means amber inside the last quarter of the band:
 * a class with a ±3 band flags amber from 2.25 points of deviation.
 */
export interface AlertPolicy {
  watchFraction?: number;   // 0 < f < 1
  label?: string;           // shown in the interpretation guide / tooltip
}

export interface AssetClass {
  id: string;
  label: string;
  goalId: string;
  targetPct: Percent;
  bandPct: Percent;        // half-width; the band is target ± bandPct
  currentPct: Nullable<Percent>;     // was Percent — null at a wiped plan
  value: Money;            // plane-sensitive
  /** One entry per performance.periods, same order. null where unreached. */
  returns: Nullable<Percent>[];
  /** True if this class is illiquid and has a privateCashflows series. */
  isPrivate?: boolean;
  /**
   * Engine-supplied status. Wins over the fallback rule. Use this when the
   * rule is anything richer than a threshold on current deviation — for
   * example persistence (outside for n consecutive periods), direction of
   * travel, or a policy that treats over- and under-weight asymmetrically.
   */
  alert?: AlertLevel;
}

export interface Allocation {
  goals: Goal[];
  /** Must sum to 100 on currentPct and on targetPct, to 0.1. */
  classes: AssetClass[];
  /** Absent ⇒ no amber anywhere. See AlertPolicy. */
  alertPolicy?: AlertPolicy;
}

/* ---- 3. Performance ---------------------------------------------- */

export interface Performance {
  /** Column headers, e.g. ["1Q","YTD","1Y","3Y","5Y","10Y"]. */
  periods: string[];
  /** First index that is annualised rather than a period return. */
  annualisedFromIndex: number;
  total: Nullable<Percent>[];
  benchmark?: Nullable<Percent>[];
  benchmarkLabel?: string;
  footnote?: string;
}

/* ---- 4. Liquidity ------------------------------------------------ */

export interface LiquidityTier {
  id: string;
  /** 1 | 2 | 3, or omitted for the illiquid remainder. */
  tier?: 1 | 2 | 3;
  label: string;
  note: string;
  value: Money;
  colour?: string;
  /** false excludes the tier from cover ratios. Default true. */
  liquid?: boolean;
  /** Which classes rolled into this tier. Required for audit; unused by the UI. */
  classIds?: string[];
}

export interface Liquidity {
  tiers: LiquidityTier[];
  /** All positive magnitudes except net. */
  forecast12m: {
    distributions: Money;
    income: Money;
    calls: Money;
    payout: Money;
    net: Money;
  };
  payoutLabel?: string;
  unfundedToNav?: Ratio;
  /** WP3.10 §5 steady-state anchor. Drawn as a reference line. */
  coverageAnchor?: Ratio;
  /** P-B. Above this, coverage renders in the alert colour. UNSET until P-B is filled. */
  coverageDanger?: Ratio;
  /**
   * unfunded ÷ (cash + every non-private sleeve value) for the active
   * plane's as-of quarter — the same liquid base as tiers t1+t2. This is
   * P-B's binding ratio (decision_metrics.py's liquidity_shortfall_probability
   * docstring: breaching 1.0 means unfunded commitments exceed everything
   * sellable). The E1 measurement (docs/superpowers/specs/2026-08-15-
   * e1-overcommitment-measurement.md) found it monotone in the player's
   * allocation while forced secondaries stayed unreachable — cov-01's
   * teaching surface, in place of unfundedToNav.
   */
  unfundedToLiquid?: Ratio;
  /** Always 1.0 — decision_metrics.py's binding-ratio breach line (cov-01). */
  breachLine?: Ratio;
  /** Running maximum of unfundedToLiquid over every CLOSED quarter so far. */
  worstUnfundedToLiquid?: Ratio;
  /** How the next 12 months of outflow is met. Should sum to the gross outflow. */
  sourcing?: { label: string; value: Money; colour?: string }[];
  tierFootnote?: string;
  flowFootnote?: string;
  sourcingFootnote?: string;
}

/* ---- 5. Private cashflows ---------------------------------------- */

export interface PrivateQuarter {
  label: string;            // "Y4Q3"
  forecast: boolean;        // true ⇒ mechanical roll-forward, labelled as such
  calls: Money;             // positive magnitude
  distributions: Money;     // positive magnitude
  net: Money;               // distributions − calls
  navOpen: Money;
  navClose: Money;
  unfundedOpen: Money;
  unfundedClose: Money;
  callRateUnfunded: Nullable<Ratio>; // was Ratio — null when opening unfunded is 0
  callRateNav: Nullable<Ratio>;      // was Ratio — null when opening NAV is 0
  coverage: Nullable<Ratio>;         // was Ratio — null when closing NAV is 0
  /**
   * Undrawn commitment CANCELLED this quarter at the end of a cohort's
   * contractual life (ER-6's terminal lapse). Positive magnitude, 0.0 in
   * most quarters. It leaves the unfunded balance without ever being
   * called — never treat it as a call.
   */
  expiredUndrawn: Money;
}

/**
 * The programme's cohort NAV stack at the as-of quarter, oldest vintage
 * first (cio-03b — the successor to the retired PrivateMarkets.ladderSummary).
 * True NAV only: a per-cohort REPORTED (appraisal-smoothed) mark is not
 * tracked anywhere in the engine, so it is not carried here — see
 * PrivateCashflows.footnote before assuming one exists.
 */
export interface VintageRung {
  id: string;
  label: string;
  navTrue: Money;
}

export interface PrivateCashflows {
  /** Number of realised quarters. Everything from this index on is forecast. */
  histCount: number;
  classes: { id: string; label: string }[];
  aggregateLabel?: string;
  /**
   * Keyed by asset-class id, plus "aggregate". Every series must be the
   * same length and share the same quarter labels in the same order.
   */
  series: Record<string, PrivateQuarter[]>;
  /** Optional so a payload built before cio-03b still type-checks. */
  vintages?: VintageRung[];
  footnote?: string;
}

/* ---- 6. Markets --------------------------------------------------- */

export interface MarketSeries {
  id: string;
  label: string;
  colour: string;
  /** Decimal places for axis and endpoint labels. */
  dp?: number;
  /** Only for level series (rates, spreads): "%", "bps". */
  unit?: string;
  /** Monthly, oldest first, same length as plan.history.values. */
  path: number[];
  /** Only on indexed return series. One per performance.periods. */
  returns?: Nullable<Percent>[];
}

export interface Markets {
  tiles?: { label: string; value: string; sub?: string; tone?: "warn" }[];
  /** Indexed to 100 at the start of the window. */
  returns?: MarketSeries[];
  /** Level series — the macro state. See DN-8 §O-3 before shipping to the public tier. */
  conditions?: MarketSeries[];
  correlations?: { id: string; label: string; current: number; baseline: number }[];
  correlationNote?: string;
  returnsFootnote?: string;
  conditionsFootnote?: string;
  correlationFootnote?: string;
}

/* ==================================================================
 *  BUILDER SIGNATURE
 * ================================================================== */

export interface BuildOptions {
  plane: Plane;
  /** Months since world start. Defaults to the run cursor. */
  asOfMonth?: number;
  /** Quarters of forecast to append. 0 suppresses the forecast entirely. */
  forecastQuarters?: number;
}

export type BuildCioView = (runRecord: unknown, opts: BuildOptions) => CioView;

/* ==================================================================
 *  VALIDATOR
 *  Run in dev and in CI against a golden RunRecord. Cheap, and it
 *  catches the failure modes that render as plausible nonsense
 *  rather than as a crash.
 * ================================================================== */

export function validateCioView(v: CioView): string[] {
  const e: string[] = [];
  const near = (a: number, b: number, tol = 0.1) => Math.abs(a - b) <= tol;
  const finite = (x: unknown) => typeof x === "number" && Number.isFinite(x);

  if (!v.meta?.runId) e.push("meta.runId is required — the footer traceability claim depends on it");
  if (!v.meta?.linkageVersion) e.push("meta.linkageVersion is required and is disclosed on screen");
  if (!v.meta?.planesAvailable?.includes(v.meta?.plane)) e.push("meta.plane is not in meta.planesAvailable");

  // allocation closes
  const cur = v.allocation.classes.reduce((s, c) => s + (c.currentPct || 0), 0);
  const tgt = v.allocation.classes.reduce((s, c) => s + c.targetPct, 0);
  if (!near(cur, 100)) e.push(`allocation.classes currentPct sums to ${cur.toFixed(2)}, expected 100`);
  if (!near(tgt, 100)) e.push(`allocation.classes targetPct sums to ${tgt.toFixed(2)}, expected 100`);

  // every class has a goal, every goal has classes
  const goalIds = new Set(v.allocation.goals.map((g) => g.id));
  v.allocation.classes.forEach((c) => {
    if (!goalIds.has(c.goalId)) e.push(`class ${c.id} references unknown goal ${c.goalId}`);
    if (c.returns && c.returns.length !== v.performance.periods.length)
      e.push(`class ${c.id} has ${c.returns.length} returns, expected ${v.performance.periods.length}`);
    if (c.bandPct < 0) e.push(`class ${c.id} has a negative band`);
  });

  // alert policy and explicit levels
  const ap = v.allocation.alertPolicy;
  if (ap && ap.watchFraction != null && !(ap.watchFraction > 0 && ap.watchFraction < 1))
    e.push(`allocation.alertPolicy.watchFraction is ${ap.watchFraction}, expected between 0 and 1 exclusive`);
  if (!ap || ap.watchFraction == null) {
    const anyExplicit = v.allocation.classes.some((c) => c.alert);
    if (!anyExplicit) e.push("no alertPolicy.watchFraction and no explicit class.alert — amber will never fire, only breaches will flag");
  }
  const explicit = v.allocation.classes.filter((c) => c.alert).length;
  if (explicit > 0 && explicit < v.allocation.classes.length)
    e.push(`${explicit} of ${v.allocation.classes.length} classes carry an explicit alert — supply it for all or for none, mixed sources are not auditable`);
  v.allocation.classes.forEach((c) => {
    if (!c.alert) return;
    const d = Math.abs((c.currentPct || 0) - c.targetPct);
    if (c.alert === "breach" && d <= c.bandPct) e.push(`class ${c.id} is flagged breach but sits inside its band — intended?`);
    if (c.alert === "ok" && d > c.bandPct) e.push(`class ${c.id} is flagged ok but sits outside its band — intended?`);
  });
  v.allocation.goals.forEach((g) => {
    if (g.tolerancePct != null && g.tolerancePct <= 0) e.push(`goal ${g.id} has a non-positive tolerancePct`);
    if (g.tolerancePct == null && !g.alert) e.push(`goal ${g.id} has neither tolerancePct nor alert — it will never flag`);
  });

  // classes are grouped by goal in declared order — the donut assumes it
  const order = v.allocation.classes.map((c) => v.allocation.goals.findIndex((g) => g.id === c.goalId));
  for (let i = 1; i < order.length; i++) {
    if (order[i] < order[i - 1]) { e.push("allocation.classes are not grouped in goal order"); break; }
  }

  // returns arrays are the right length
  if (v.performance.total.length !== v.performance.periods.length) e.push("performance.total length ≠ periods length");
  if (v.performance.benchmark && v.performance.benchmark.length !== v.performance.periods.length)
    e.push("performance.benchmark length ≠ periods length");

  // liquidity closes against the plan
  const tierSum = v.liquidity.tiers.reduce((s, t) => s + t.value, 0);
  if (!near(tierSum, v.plan.totalValue, v.plan.totalValue * 0.005))
    e.push(`liquidity tiers sum to ${tierSum.toFixed(0)}, plan total is ${v.plan.totalValue.toFixed(0)}`);

  const f = v.liquidity.forecast12m;
  if (f) {
    [["distributions", f.distributions], ["income", f.income], ["calls", f.calls], ["payout", f.payout]].forEach(([k, x]) => {
      if (finite(x) && (x as number) < 0) e.push(`liquidity.forecast12m.${k} must be a positive magnitude`);
    });
    const net = f.distributions + f.income - f.calls - f.payout;
    if (!near(net, f.net, 1)) e.push(`liquidity.forecast12m.net is ${f.net}, components imply ${net.toFixed(1)}`);
  }
  (["unfundedToLiquid", "worstUnfundedToLiquid"] as const).forEach((k) => {
    const val = v.liquidity[k];
    if (finite(val) && (val as number) < 0) e.push(`liquidity.${k} must be a non-negative ratio`);
  });
  if (v.liquidity.breachLine != null && v.liquidity.breachLine !== 1.0)
    e.push(`liquidity.breachLine is ${v.liquidity.breachLine}, expected exactly 1.0`);

  // private series are aligned and internally consistent
  const pcf = v.privateCashflows;
  if (pcf) {
    const agg = pcf.series.aggregate;
    if (!agg) e.push("privateCashflows.series.aggregate is required");
    const n = agg?.length ?? 0;
    if (pcf.histCount > n) e.push("privateCashflows.histCount exceeds series length");
    Object.entries(pcf.series).forEach(([k, rows]) => {
      if (rows.length !== n) e.push(`private series ${k} has length ${rows.length}, aggregate has ${n}`);
      rows.forEach((r, i) => {
        if (r.calls < 0 || r.distributions < 0) e.push(`${k} ${r.label}: calls and distributions must be positive magnitudes`);
        if (!near(r.net, r.distributions - r.calls, 0.5)) e.push(`${k} ${r.label}: net ≠ distributions − calls`);
        if (agg && rows[i].label !== agg[i].label) e.push(`${k} quarter ${i} label does not match aggregate`);
        if ((i >= pcf.histCount) !== r.forecast) e.push(`${k} ${r.label}: forecast flag disagrees with histCount`);
      });
    });
    // aggregate really is the sum
    if (agg) {
      agg.forEach((r, i) => {
        const s = pcf.classes.reduce((acc, c) => acc + (pcf.series[c.id]?.[i]?.calls ?? 0), 0);
        if (!near(s, r.calls, Math.max(0.5, r.calls * 0.001))) e.push(`aggregate calls at ${r.label} ≠ sum of classes`);
        const sExp = pcf.classes.reduce((acc, c) => acc + (pcf.series[c.id]?.[i]?.expiredUndrawn ?? 0), 0);
        const rExp = r.expiredUndrawn ?? 0;
        if (!near(sExp, rExp, Math.max(0.5, rExp * 0.001))) e.push(`aggregate expiredUndrawn at ${r.label} ≠ sum of classes`);
      });
    }
  }

  // markets paths align with the plan window
  const hLen = v.plan.history.values.length;
  v.markets?.returns?.concat(v.markets?.conditions ?? []).forEach((s) => {
    if (s.path.length !== hLen) e.push(`market series ${s.id} has ${s.path.length} points, plan history has ${hLen}`);
  });

  // zeros where nulls belong — the failure that renders as a plausible lie
  const zeroWhereNull = (arr: Nullable<number>[] | undefined, where: string) => {
    if (!arr) return;
    arr.forEach((x, i) => { if (x === 0) e.push(`${where}[${i}] is exactly 0 — confirm this is a real zero and not an unreached period`); });
  };
  zeroWhereNull(v.performance.total, "performance.total");
  zeroWhereNull(v.performance.benchmark, "performance.benchmark");

  return e;
}
