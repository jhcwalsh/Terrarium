/* ==================================================================
 *  TERRARIUM — CIO DASHBOARD  ·  v0.3
 *
 *  This component is a PURE RENDERER. It computes nothing that is
 *  scoreable, disclosed, or governed. Everything it draws arrives in
 *  a single `view` prop conforming to CioView (see cioView.ts and
 *  DN-8 for the contract).
 *
 *  Contract summary — DN-8 §3 has the full field list:
 *    · percentages are numbers in percentage points (26.1, not 0.261)
 *    · money is served in the unit named by meta.unitLabel ("$m", 1 point
 *      = $1m declared) — but this renderer no longer echoes that caption
 *      or scales by it directly. Every money figure goes through usd()
 *      (lib/money.ts), which re-denominates the SAME served points as a
 *      $10bn book (app-open-01 review round fix 1); meta.unitLabel/
 *      unitSuffix are otherwise unused here.
 *    · calls, distributions and payout are POSITIVE MAGNITUDES; the
 *      renderer applies sign. net = distributions − calls.
 *    · any period the run has not reached must be null, never 0.
 *    · every forecast row carries forecast: true and is a mechanical
 *      roll-forward, not a projection. The renderer labels it as such
 *      and that label is not optional.
 * ================================================================== */

import { useState, useMemo, useContext, createContext, Fragment } from "react";
import type { ReactNode } from "react";
import type {
  CioView,
  Plane,
  Allocation,
  AlertLevel,
  AlertPolicy,
  Goal,
  AssetClass,
  PrivateQuarter,
  MarketSeries,
  VintageRung,
} from "../lib/cioView";
import { DENOMINATION_NOTE, usd } from "../lib/money";

/* ---------------------------------------------------------------- *
 *  THEME
 * ---------------------------------------------------------------- */

/* Mirrors app/src/styles.css :root — keep in sync by hand; shade() needs
 * literal hex, so CSS vars can't flow through here. */
const C = {
  ink: "#0a1d1f", // --glass
  panel: "#0f282b", // --panel
  well: "#143439", // --panel2
  rule: "#20464b", // --line
  ruleSoft: "#18383c", // --hair
  ice: "#d7e6e3", // --ice
  mist: "#7c9b99", // --muted
  faint: "#54726f", // --dim
  warn: "#d2624f", // --clay
  good: "#4fc3a1", // --jade
  amber: "#d6a24a", // --brass
  blue: "#6e9bd1",
};

const F = {
  display: '"Bricolage Grotesque", sans-serif',
  body: "Archivo, system-ui, sans-serif",
  mono: '"IBM Plex Mono", monospace',
};

const GOAL_COLOUR: Record<string, string> = {
  growth: "#d6a24a",
  real: "#4fc3a1",
  income: "#6e9bd1",
  diversifier: "#a88bc4",
};
const FALLBACK = ["#d6a24a", "#4fc3a1", "#6e9bd1", "#a88bc4", "#d2624f", "#7c9b99"];
const goalColour = (id: string, i: number) => GOAL_COLOUR[id] || FALLBACK[i % FALLBACK.length];

/* ---------------------------------------------------------------- *
 *  FORMATTING — the only place units become strings
 * ---------------------------------------------------------------- */

const NA = "—";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

// app-open-01 review round fix 1: the local money() helper (which read
// meta.unitLabel/unitSuffix and used a unicode minus sign) is retired.
// Every money figure in this component now renders through usd() from
// lib/money.ts — one dollar language across the whole app, ASCII "-" for
// every negative, and the same $10bn book denomination as Reckoning/Play.
const pct = (v: number | null | undefined, d = 1) => (isNum(v) ? `${v.toFixed(d)}%` : NA);
const sgn = (v: number | null | undefined, d = 1) => (isNum(v) ? (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d) : NA);
const num = (v: number | null | undefined, d = 2) => (isNum(v) ? v.toFixed(d) : NA);

/* ---------------------------------------------------------------- *
 *  ALERTS
 *  Levels come from the engine when supplied (class.alert / goal.alert).
 *  Fallback: "breach" is |dev| > band, which needs no parameter.
 *  "watch" needs a threshold, so it renders ONLY when the payload
 *  supplies allocation.alertPolicy.watchFraction. The renderer does
 *  not carry a default — see DN-8 §7.
 * ---------------------------------------------------------------- */

const ALERT_COLOUR: Record<AlertLevel, string | null> = { breach: C.warn, watch: C.amber, ok: null };

function alertLevel(
  cur: number | null | undefined,
  target: number | null | undefined,
  band: number | null | undefined,
  policy: AlertPolicy | undefined,
  explicit: AlertLevel | undefined,
): AlertLevel {
  if (explicit) return explicit;
  if (!isNum(cur) || !isNum(target) || !isNum(band) || band <= 0) return "ok";
  const d = Math.abs(cur - target);
  if (d > band) return "breach";
  const wf = policy && isNum(policy.watchFraction) ? policy.watchFraction : null;
  if (wf !== null && d >= wf * band) return "watch";
  return "ok";
}

function AlertFlag({ level, dir, label }: { level: AlertLevel | null | undefined; dir: number; label: string }) {
  if (!level || level === "ok") return <span style={{ display: "inline-block", width: 15 }} />;
  const c = ALERT_COLOUR[level] ?? undefined;
  const up = dir >= 0;
  return (
    <span title={label} style={{ display: "inline-flex", width: 15, justifyContent: "center", verticalAlign: "middle" }}>
      <svg width="11" height="11" viewBox="0 0 10 10" role="img" aria-label={label}>
        <path d={up ? "M5 1.1 L9.3 8.6 L0.7 8.6 Z" : "M5 8.9 L0.7 1.4 L9.3 1.4 Z"}
          fill={level === "breach" ? c : "none"} stroke={c} strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function allocationAlerts(allocation: Allocation): { breach: number; watch: number; policy: AlertPolicy | undefined } {
  const policy = allocation.alertPolicy;
  let breach = 0, watch = 0;
  allocation.classes.forEach((c) => {
    const l = alertLevel(c.currentPct, c.targetPct, c.bandPct, policy, c.alert);
    if (l === "breach") breach++; else if (l === "watch") watch++;
  });
  return { breach, watch, policy };
}

function AlertSummary({ counts }: { counts: { breach: number; watch: number; policy?: AlertPolicy } }) {
  if (!counts.breach && !counts.watch) {
    return <span style={{ font: `12px ${F.body}`, color: C.faint }}>All classes inside band</span>;
  }
  return (
    <span style={{ display: "flex", gap: 14, alignItems: "center", font: `12px ${F.body}` }}>
      {counts.breach > 0 && (
        <span style={{ display: "flex", alignItems: "center", gap: 5, color: C.warn }}>
          <AlertFlag level="breach" dir={1} label="outside band" />
          {counts.breach} outside band
        </span>
      )}
      {counts.watch > 0 && (
        <span style={{ display: "flex", alignItems: "center", gap: 5, color: C.amber }}>
          <AlertFlag level="watch" dir={1} label="approaching band" />
          {counts.watch} approaching
        </span>
      )}
    </span>
  );
}

/* ---------------------------------------------------------------- *
 *  CONTEXT
 * ---------------------------------------------------------------- */

const ViewCtx = createContext<CioView | null>(null);
const useView = () => useContext(ViewCtx)!;

/* ---------------------------------------------------------------- *
 *  PRIMITIVES
 * ---------------------------------------------------------------- */

function Panel({
  title,
  note,
  right,
  children,
  style,
}: {
  title: string;
  note?: React.ReactNode;
  right?: React.ReactNode;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <section style={{ background: C.panel, border: `1px solid ${C.rule}`, borderRadius: 3, padding: "14px 16px 16px", ...style }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <h2 style={{ font: `500 11px ${F.body}`, letterSpacing: "0.16em", textTransform: "uppercase", color: C.mist, margin: 0 }}>{title}</h2>
        {note && <span style={{ font: `12px ${F.body}`, color: C.faint }}>{note}</span>}
        <div style={{ marginLeft: "auto" }}>{right}</div>
      </div>
      {children}
    </section>
  );
}

function Tile({
  label,
  value,
  sub,
  tone,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: string;
}) {
  return (
    <div style={{ flex: "1 1 150px", minWidth: 140, padding: "11px 13px", background: C.well, border: `1px solid ${C.rule}` }}>
      <div style={{ font: `10px ${F.body}`, letterSpacing: "0.12em", color: C.faint, textTransform: "uppercase" }}>{label}</div>
      <div style={{ font: `600 22px ${F.mono}`, color: tone || C.ice, marginTop: 4, lineHeight: 1.1 }}>{value}</div>
      {sub && <div style={{ font: `12px ${F.body}`, color: C.faint, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function Legend({ items }: { items: { label: string; c: string; w?: number; dash?: boolean }[] }) {
  return (
    <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
      {items.map((i) => (
        <span key={i.label} style={{ display: "flex", alignItems: "center", gap: 6, font: `12px ${F.body}`, color: C.mist }}>
          <span style={{ width: 14, height: 0, borderTop: `${i.w || 2}px ${i.dash ? "dashed" : "solid"} ${i.c}` }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

function Empty({ what }: { what: string }) {
  return <div style={{ padding: "22px 0", font: `13px ${F.body}`, color: C.faint, textAlign: "center" }}>No {what} in this payload.</div>;
}

/* ---------------------------------------------------------------- *
 *  PLAN — growth
 * ---------------------------------------------------------------- */

export type PlanWindow = "3y" | "full";

/** How many trailing months of `plan.history.values` a window mode shows —
 * capped at what actually exists, never invented (app-open-01 item 3:
 * "read the series length it plots"). */
export function planWindowMonths(totalMonths: number, mode: PlanWindow): number {
  return mode === "full" ? totalMonths : Math.min(36, totalMonths);
}

/** The trailing slice of plan.history a window mode actually plots — the
 * one array both the chart and its header label read, so the label can
 * never claim a window the chart isn't showing. */
export function planWindowSlice(
  values: number[],
  worldStartIndex: number,
  mode: PlanWindow,
): { values: number[]; worldStartIndex: number } {
  const shown = planWindowMonths(values.length, mode);
  const from = values.length - shown;
  return { values: values.slice(from), worldStartIndex: Math.max(0, worldStartIndex - from) };
}

/**
 * The chart header's timeframe label (app-open-01 item 3). Driven entirely
 * by the ACTUAL plotted window (`shownMonths`, from `planWindowSlice`) and
 * how much of it is still the inherited pre-history (`inheritedMonths`) —
 * never a hardcoded "past 3 years" divorced from what the SVG below it
 * draws.
 *
 * ER-13's honesty marker travels with the label rather than inventing new
 * wording: the chart already carries "INHERITED DECADE (SIMULATED)"
 * (plan.preRunLabel, cio-04) inside the hatched band itself, directly below
 * this label — the qualifier here names the SAME fact in three words so a
 * reader does not have to reach the chart body to learn it.
 */
export function planWindowLabel(
  shownMonths: number,
  inheritedMonths: number,
  mode: PlanWindow,
): string {
  const years = shownMonths / 12;
  const yearsText = Number.isInteger(years) ? String(years) : years.toFixed(1);
  const base =
    mode === "full"
      ? `FULL RANGE — ${yearsText}Y`
      : `PAST ${yearsText} YEAR${years === 1 ? "" : "S"}`;
  if (inheritedMonths <= 0) return base;
  if (inheritedMonths >= shownMonths) return `${base} (INHERITED, SIMULATED)`;
  return `${base} (PARTLY INHERITED)`;
}

function PlanGrowth() {
  const { plan, meta } = useView();
  const [mode, setMode] = useState<PlanWindow>("3y");
  const full = plan.history;
  if (!full || !full.values || !full.values.length) return <Empty what="plan history" />;

  // the toggle only earns its place when "3y" and "full" would actually
  // differ — a world younger than 3 years already shows everything.
  const canWindow = full.values.length > planWindowMonths(full.values.length, "3y");
  const p = planWindowSlice(full.values, full.worldStartIndex ?? 0, mode);
  const inheritedShown = Math.max(0, Math.min(p.worldStartIndex, p.values.length));
  const timeframeLabel = planWindowLabel(p.values.length, inheritedShown, mode);

  const N = p.values.length - 1;
  const START = Math.max(0, Math.min(p.worldStartIndex == null ? 0 : p.worldStartIndex, N));
  const W = 900, H = 230, L = 56, R = 16, T = 22, B = 26;
  const vals = p.values.filter(isNum);
  const pad = (Math.max(...vals) - Math.min(...vals)) * 0.18 || 1;
  const lo = Math.min(...vals) - pad, hi = Math.max(...vals) + pad;
  const x = (m: number) => L + (m / N) * (W - L - R);
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const seg = (a: number, b: number) => p.values.slice(a, b + 1).map((v, i) => `${i ? "L" : "M"}${x(a + i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const pre = seg(0, START), post = seg(START, N);
  const xTicks: number[] = []; for (let m = N; m >= 0; m -= 12) xTicks.unshift(m);

  return (
    <div>
      <div
        className="plan-growth-header"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8, marginBottom: 6 }}
      >
        <span
          className="plan-growth-timeframe"
          style={{ font: `600 11px ${F.body}`, letterSpacing: "0.12em", textTransform: "uppercase", color: C.mist }}
        >
          {timeframeLabel}
        </span>
        {canWindow && (
          <div style={{ display: "flex", gap: 4 }}>
            {(["3y", "full"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  padding: "3px 9px", cursor: "pointer", borderRadius: 2, font: `11px ${F.body}`,
                  border: `1px solid ${mode === m ? C.ice : C.rule}`,
                  background: mode === m ? C.ice : "transparent", color: mode === m ? C.ink : C.mist,
                }}
              >
                {m === "3y" ? "3Y" : "Full range"}
              </button>
            ))}
          </div>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <defs>
        <linearGradient id="pgPost" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={C.good} stopOpacity="0.28" /><stop offset="100%" stopColor={C.good} stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="pgPre" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={C.faint} stopOpacity="0.16" /><stop offset="100%" stopColor={C.faint} stopOpacity="0.01" />
        </linearGradient>
        <pattern id="pgHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke={C.rule} strokeWidth="1" opacity="0.55" />
        </pattern>
      </defs>

      {START > 0 && (
        <g>
          <rect x={L} y={T} width={x(START) - L} height={H - T - B} fill="url(#pgHatch)" opacity={0.5} />
          <rect x={L} y={T} width={x(START) - L} height={H - T - B} fill={C.ink} opacity={0.35} />
        </g>
      )}

      {[0.15, 0.4, 0.65, 0.9].map((f) => {
        const v = lo + (hi - lo) * f;
        return (
          <g key={f}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={C.ruleSoft} />
            <text x={L - 8} y={y(v) + 3.5} textAnchor="end" fill={C.faint} style={{ font: `11px ${F.mono}` }}>
              {v >= 1000 ? `${(v / 1000).toFixed(1)}bn` : Math.round(v)}
            </text>
          </g>
        );
      })}

      {START > 0 && <path d={`${pre} L${x(START)},${y(lo)} L${x(0)},${y(lo)} Z`} fill="url(#pgPre)" />}
      <path d={`${post} L${x(N)},${y(lo)} L${x(START)},${y(lo)} Z`} fill="url(#pgPost)" />
      {START > 0 && <path d={pre} fill="none" stroke={C.faint} strokeWidth={1.8} strokeDasharray="5 3" />}
      <path d={post} fill="none" stroke={C.good} strokeWidth={2.2} />

      {START > 0 && (
        <g>
          <line x1={x(START)} x2={x(START)} y1={T - 8} y2={H - B} stroke={C.amber} strokeWidth={1.2} />
          <circle cx={x(START)} cy={y(p.values[START])} r={3} fill={C.amber} />
          <text x={(L + x(START)) / 2} y={T - 8} textAnchor="middle" fill={C.faint} style={{ font: `9.5px ${F.body}`, letterSpacing: "0.14em" }}>
            {(plan.preRunLabel || "Before the world").toUpperCase()}
          </text>
          <text x={x(START) + 8} y={T - 8} fill={C.amber} style={{ font: `600 9.5px ${F.body}`, letterSpacing: "0.14em" }}>
            {(plan.worldStartLabel || "World begins").toUpperCase()}
          </text>
        </g>
      )}

      {xTicks.map((m) => (
        <text key={m} x={x(m)} y={H - 8} textAnchor="middle" fill={m < START ? C.faint : C.mist} style={{ font: `11px ${F.body}` }}>
          {m === N ? "now" : `−${((N - m) / 12).toFixed(0)}y`}
        </text>
      ))}
      <circle cx={x(N)} cy={y(p.values[N])} r={3.5} fill={C.good} />
      {meta.plane === "true" && (
        <text x={W - R} y={T + 2} textAnchor="end" fill={C.mist} style={{ font: `10px ${F.body}`, letterSpacing: "0.1em" }}>TRUE PLANE</text>
      )}
      </svg>
    </div>
  );
}

/* ---------------------------------------------------------------- *
 *  PLAN — allocation donut
 * ---------------------------------------------------------------- */

function shade(hex: string, f: number): string {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const m = (v: number) => Math.round(f < 0 ? v * (1 + f) : v + (255 - v) * f);
  return `rgb(${m(r)},${m(g)},${m(b)})`;
}
function arcPath(cx: number, cy: number, r0: number, r1: number, a0: number, a1: number): string {
  const rad = (a: number) => ((a - 90) * Math.PI) / 180;
  const p = (r: number, a: number): [number, number] => [cx + r * Math.cos(rad(a)), cy + r * Math.sin(rad(a))];
  const big = a1 - a0 > 180 ? 1 : 0;
  const [x0, y0] = p(r1, a0), [x1, y1] = p(r1, a1), [x2, y2] = p(r0, a1), [x3, y3] = p(r0, a0);
  return `M${x0},${y0} A${r1},${r1} 0 ${big} 1 ${x1},${y1} L${x2},${y2} A${r0},${r0} 0 ${big} 0 ${x3},${y3} Z`;
}

interface InnerArc extends Goal { a0: number; a1: number; tot: number; mid: number; c: string; }
interface OuterArc extends AssetClass { a0: number; a1: number; mid: number; c: string; }
interface Label extends OuterArc { ax: number; ay: number; ex: number; ey: number; right: boolean; x: number; y: number; }

function AllocationDonut() {
  const { allocation, plan } = useView();
  const policy = allocation.alertPolicy;
  const wf = policy && isNum(policy.watchFraction) ? policy.watchFraction : null;
  const W = 560, H = 420, cx = 268, cy = 208;
  const R_IN0 = 78, R_IN1 = 112, R_OUT0 = 116, R_OUT1 = 148, LABEL_X = 196, GAP = 27;

  const rings = useMemo<{ inner: InnerArc[]; outer: OuterArc[] }>(() => {
    let a = 0;
    const inner: InnerArc[] = [];
    const outer: OuterArc[] = [];
    allocation.goals.forEach((g, gi) => {
      const members = allocation.classes.filter((c) => c.goalId === g.id);
      const tot = members.reduce((s, c) => s + (c.currentPct || 0), 0);
      const a0 = a, a1 = a + tot * 3.6;
      inner.push({ ...g, a0, a1, tot, mid: (a0 + a1) / 2, c: goalColour(g.id, gi) });
      let b = a0;
      members.forEach((c, i) => {
        const b1 = b + (c.currentPct || 0) * 3.6;
        outer.push({ ...c, a0: b, a1: b1, mid: (b + b1) / 2, c: shade(goalColour(g.id, gi), -0.12 * i) });
        b = b1;
      });
      a = a1;
    });
    return { inner, outer };
  }, [allocation]);

  const labels = useMemo<Label[]>(() => {
    const rad = (d: number) => ((d - 90) * Math.PI) / 180;
    const pt = (r: number, d: number): [number, number] => [cx + r * Math.cos(rad(d)), cy + r * Math.sin(rad(d))];
    const all: Label[] = rings.outer.map((s) => {
      const [ax, ay] = pt(R_OUT1 + 1, s.mid), [ex, ey] = pt(R_OUT1 + 14, s.mid);
      const right = Math.cos(rad(s.mid)) >= 0;
      return { ...s, ax, ay, ex, ey, right, y: ey, x: right ? cx + LABEL_X : cx - LABEL_X };
    });
    (["r", "l"] as const).forEach((side) => {
      const col = all.filter((l) => (side === "r" ? l.right : !l.right)).sort((p, q) => p.y - q.y);
      for (let i = 1; i < col.length; i++) if (col[i].y - col[i - 1].y < GAP) col[i].y = col[i - 1].y + GAP;
      const over = col.length ? col[col.length - 1].y - (H - 20) : 0;
      if (over > 0) {
        col[col.length - 1].y -= over;
        for (let i = col.length - 2; i >= 0; i--) if (col[i + 1].y - col[i].y < GAP) col[i].y = col[i + 1].y - GAP;
      }
    });
    return all;
  }, [rings]);

  const halo: React.CSSProperties = { stroke: C.ink, strokeWidth: 3.4, paintOrder: "stroke", strokeLinejoin: "round" };

  return (
    <div style={{ display: "flex", gap: 22, flexWrap: "wrap", alignItems: "center" }}>
      <div style={{ flex: "1 1 480px", minWidth: 340, maxWidth: 620 }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
          {labels.map((l) => (
            <path key={`ld-${l.id}`} fill="none" stroke={C.rule} strokeWidth={1}
              d={`M${l.ax.toFixed(1)},${l.ay.toFixed(1)} L${l.ex.toFixed(1)},${l.ey.toFixed(1)} L${(l.right ? l.x - 8 : l.x + 8).toFixed(1)},${l.y.toFixed(1)}`} />
          ))}
          {rings.inner.map((s) => <path key={s.id} d={arcPath(cx, cy, R_IN0, R_IN1, s.a0 + 0.5, s.a1 - 0.5)} fill={s.c} opacity={0.4} />)}
          {rings.outer.map((s) => {
            const lvl = alertLevel(s.currentPct, s.targetPct, s.bandPct, policy, s.alert);
            return (
              <Fragment key={s.id}>
                <path d={arcPath(cx, cy, R_OUT0, R_OUT1, s.a0 + 0.6, s.a1 - 0.6)} fill={s.c} opacity={0.92} />
                {lvl !== "ok" && (
                  <path d={arcPath(cx, cy, R_OUT1 - 4, R_OUT1, s.a0 + 0.6, s.a1 - 0.6)} fill={ALERT_COLOUR[lvl] ?? undefined} opacity={lvl === "breach" ? 0.95 : 0.8} />
                )}
              </Fragment>
            );
          })}

          {rings.inner.map((s) => {
            const r = (R_IN0 + R_IN1) / 2, t = ((s.mid - 90) * Math.PI) / 180;
            const lx = cx + r * Math.cos(t), ly = cy + r * Math.sin(t);
            return (
              <g key={`gl-${s.id}`}>
                <text x={lx} y={ly - 3} textAnchor="middle" fill={C.ice} style={{ font: `600 10px ${F.body}`, letterSpacing: "0.1em", ...halo }}>
                  {s.label.toUpperCase()}
                </text>
                <text x={lx} y={ly + 14} textAnchor="middle" fill={C.ice} style={{ font: `600 16px ${F.mono}`, ...halo }}>{s.tot.toFixed(1)}</text>
              </g>
            );
          })}

          {labels.map((l) => (
            <g key={`lb-${l.id}`}>
              <circle cx={l.right ? l.x - 8 : l.x + 8} cy={l.y} r={2} fill={l.c} />
              <text x={l.x} y={l.y - 2} textAnchor={l.right ? "start" : "end"} fill={C.ice} style={{ font: `12px ${F.body}` }}>{l.label}</text>
              <text x={l.x} y={l.y + 12} textAnchor={l.right ? "start" : "end"}
                fill={ALERT_COLOUR[alertLevel(l.currentPct, l.targetPct, l.bandPct, policy, l.alert)] || C.faint}
                style={{ font: `11px ${F.mono}` }}>{pct(l.currentPct)}</text>
            </g>
          ))}

          {/* app-open-01 item 1 (owner ruling 2026-08-16): the CIO's headline
              value is the $10bn display denomination (money.ts's usd()),
              not the raw meta.unitLabel figure — plan.totalValue is still
              the same scored points, only the rendering changed. */}
          <text x={cx} y={cy - 6} textAnchor="middle" fill={C.ice} style={{ font: `500 25px ${F.mono}` }}>{usd(plan.totalValue)}</text>
          <text x={cx} y={cy + 12} textAnchor="middle" fill={C.faint} style={{ font: `10px ${F.body}`, letterSpacing: "0.16em" }}>TOTAL PLAN</text>
        </svg>
      </div>

      <div style={{ flex: "1 1 250px", minWidth: 240 }}>
        <div style={{ display: "flex", font: `10px ${F.body}`, color: C.faint, letterSpacing: "0.1em", paddingBottom: 6 }}>
          <span style={{ flex: 1 }}>GOAL</span>
          <span style={{ width: 46, textAlign: "right" }}>NOW</span>
          <span style={{ width: 40, textAlign: "right" }}>TGT</span>
          <span style={{ width: 44, textAlign: "right" }}>DEV</span>
        </div>
        {rings.inner.map((s) => {
          const tgt = allocation.classes.filter((c) => c.goalId === s.id).reduce((a, c) => a + c.targetPct, 0);
          const tol = s.tolerancePct;
          const dev = s.tot - tgt;
          const level = alertLevel(s.tot, tgt, tol, policy, s.alert);
          const flagLabel = level === "ok" ? "" :
            `${Math.abs(dev).toFixed(1)} points ${dev >= 0 ? "above" : "below"} the goal target of ${tgt.toFixed(1)}%`;
          const zoneW = wf === null || !isNum(tol) ? 0 : (1 - wf) * tol;
          return (
            <div key={s.id} style={{ padding: "8px 0", borderTop: `1px solid ${C.ruleSoft}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 9, height: 9, background: s.c, display: "inline-block" }} />
                <span style={{ flex: 1, font: `13px ${F.body}`, color: C.ice }}>{s.label}</span>
                <span style={{ width: 46, textAlign: "right", font: `14px ${F.mono}`, color: C.ice }}>{s.tot.toFixed(1)}</span>
                <span style={{ width: 40, textAlign: "right", font: `13px ${F.mono}`, color: C.faint }}>{tgt.toFixed(1)}</span>
                <span style={{ width: 44, textAlign: "right", font: `13px ${F.mono}`, color: ALERT_COLOUR[level] || C.faint }}>{sgn(dev)}</span>
                <AlertFlag level={level} dir={dev} label={flagLabel} />
              </div>
              <div style={{ position: "relative", height: 6, background: C.well, marginTop: 6, marginLeft: 17, marginRight: 15 }}>
                {isNum(tol) && (
                  <div style={{ position: "absolute", top: 0, bottom: 0, left: `${tgt - tol}%`, width: `${2 * tol}%`, background: "rgba(88,180,158,0.16)" }} />
                )}
                {zoneW > 0 && isNum(tol) && wf !== null && (
                  <Fragment>
                    <div style={{ position: "absolute", top: 0, bottom: 0, left: `${tgt - tol}%`, width: `${zoneW}%`, background: "rgba(240,196,106,0.2)" }} />
                    <div style={{ position: "absolute", top: 0, bottom: 0, left: `${tgt + wf * tol}%`, width: `${zoneW}%`, background: "rgba(240,196,106,0.2)" }} />
                  </Fragment>
                )}
                <div style={{ position: "absolute", top: 0, bottom: 0, left: 0, width: `${s.tot}%`, background: ALERT_COLOUR[level] || s.c, opacity: level === "ok" ? 0.6 : 0.75 }} />
                <div style={{ position: "absolute", top: -2, bottom: -2, left: `${tgt}%`, width: 1, background: C.ice, opacity: 0.85 }} />
              </div>
            </div>
          );
        })}
        <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 10, lineHeight: 1.5 }}>
          Inner ring is the goal split, outer ring the asset classes inside each. Tick on the bar is the policy target,
          shaded region the tolerance. A rim on the outer ring marks a class outside its band or approaching it.
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- *
 *  PLAN — performance & allocation table
 * ---------------------------------------------------------------- */

function BandBar({
  cur,
  target,
  band,
  max,
  watchFraction,
  level,
}: {
  cur: number | null;
  target: number;
  band: number;
  max: number;
  watchFraction: number | null;
  level: AlertLevel;
}) {
  const pc = (v: number | null) => `${(Math.max(0, Math.min(Number(v), max)) / max) * 100}%`;
  const wf = isNum(watchFraction) ? watchFraction : null;
  const zoneW = wf === null ? 0 : ((1 - wf) * band / max) * 100;
  const fill = level === "breach" ? "rgba(217,112,90,0.62)"
    : level === "watch" ? "rgba(240,196,106,0.5)"
    : "rgba(143,162,190,0.45)";
  return (
    <div style={{ position: "relative", height: 14, background: C.well, border: `1px solid ${C.ruleSoft}`, minWidth: 90 }}>
      {/* band */}
      <div style={{ position: "absolute", top: 0, bottom: 0, left: pc(target - band), width: `${((2 * band) / max) * 100}%`, background: "rgba(88,180,158,0.13)" }} />
      {/* watch zones — the outer slice of the band at each edge */}
      {wf !== null && (
        <Fragment>
          <div style={{ position: "absolute", top: 0, bottom: 0, left: pc(target - band), width: `${zoneW}%`, background: "rgba(240,196,106,0.16)" }} />
          <div style={{ position: "absolute", top: 0, bottom: 0, left: pc(target + wf * band), width: `${zoneW}%`, background: "rgba(240,196,106,0.16)" }} />
        </Fragment>
      )}
      <div style={{ position: "absolute", top: 3, bottom: 3, left: 0, width: pc(cur), background: fill }} />
      <div style={{ position: "absolute", top: -2, bottom: -2, left: pc(target), width: 1, background: C.ice, opacity: 0.8 }} />
    </div>
  );
}

function PerfTable() {
  const { allocation, performance } = useView();
  const periods = performance.periods;
  const policy = allocation.alertPolicy;
  const wf = policy && isNum(policy.watchFraction) ? policy.watchFraction : null;
  const max = Math.max(...allocation.classes.map((c) => Math.max(c.currentPct || 0, c.targetPct + c.bandPct))) * 1.05;

  const th: React.CSSProperties = { font: `10px ${F.body}`, letterSpacing: "0.1em", color: C.faint, textTransform: "uppercase", padding: "0 8px 7px", textAlign: "right", whiteSpace: "nowrap" };
  const td: React.CSSProperties = { font: `13px ${F.mono}`, color: C.ice, padding: "5px 8px", textAlign: "right", whiteSpace: "nowrap" };
  const ret = (v: number | null | undefined): React.CSSProperties => ({ ...td, color: !isNum(v) ? C.faint : v < 0 ? C.warn : C.ice });

  const total = performance.total;
  const benchmark = performance.benchmark;

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 860 }}>
        <thead>
          <tr>
            <th style={{ ...th, textAlign: "left", paddingLeft: 0 }}>Asset class</th>
            <th style={{ ...th, textAlign: "left" }}>Weight v target</th>
            <th style={{ ...th, textAlign: "center", padding: "0 2px 7px" }}>!</th>
            <th style={th}>Wt</th><th style={th}>Tgt</th><th style={th}>Band</th>
            <th style={{ ...th, paddingRight: 16 }}>Dev</th>
            {periods.map((p) => <th key={p} style={th}>{p}</th>)}
          </tr>
        </thead>
        <tbody>
          {allocation.goals.map((g, gi) => {
            const members = allocation.classes.filter((c) => c.goalId === g.id);
            if (!members.length) return null;
            const cur = members.reduce((a, c) => a + (c.currentPct || 0), 0);
            const tgt = members.reduce((a, c) => a + c.targetPct, 0);
            return (
              <Fragment key={g.id}>
                <tr>
                  <td colSpan={7 + periods.length} style={{ padding: "12px 0 4px" }}>
                    <span style={{ font: `600 11px ${F.body}`, letterSpacing: "0.14em", textTransform: "uppercase", color: goalColour(g.id, gi) }}>{g.label}</span>
                    <span style={{ font: `12px ${F.mono}`, color: C.faint, marginLeft: 10 }}>{pct(cur)} / {pct(tgt)}</span>
                  </td>
                </tr>
                {members.map((c) => {
                  const dev = (c.currentPct || 0) - c.targetPct;
                  const level = alertLevel(c.currentPct, c.targetPct, c.bandPct, policy, c.alert);
                  const flagLabel = level === "breach"
                    ? `${Math.abs(dev).toFixed(1)} points ${dev >= 0 ? "above" : "below"} target — outside the ±${c.bandPct} band`
                    : level === "watch"
                      ? `${Math.abs(dev).toFixed(1)} points ${dev >= 0 ? "above" : "below"} target — approaching the ±${c.bandPct} band`
                      : "";
                  return (
                    <tr key={c.id} style={{ borderTop: `1px solid ${C.ruleSoft}` }}>
                      <td style={{ ...td, textAlign: "left", paddingLeft: 0, font: `13px ${F.body}`, color: level === "breach" ? C.ice : C.mist }}>{c.label}</td>
                      <td style={{ padding: "5px 8px", width: 110 }}>
                        <BandBar cur={c.currentPct} target={c.targetPct} band={c.bandPct} max={max} watchFraction={wf} level={level} />
                      </td>
                      <td style={{ padding: "5px 2px", textAlign: "center", width: 19 }}>
                        <AlertFlag level={level} dir={dev} label={flagLabel} />
                      </td>
                      <td style={td}>{num(c.currentPct, 1)}</td>
                      <td style={{ ...td, color: C.faint }}>{num(c.targetPct, 1)}</td>
                      <td style={{ ...td, color: C.faint }}>±{num(c.bandPct, 1)}</td>
                      <td style={{ ...td, color: ALERT_COLOUR[level] || C.faint, paddingRight: 16 }}>{sgn(dev)}</td>
                      {periods.map((p, i) => <td key={p} style={ret(c.returns?.[i])}>{sgn(c.returns?.[i])}</td>)}
                    </tr>
                  );
                })}
              </Fragment>
            );
          })}

          <tr style={{ borderTop: `1px solid ${C.rule}` }}>
            <td style={{ ...td, textAlign: "left", paddingLeft: 0, font: `600 13px ${F.body}`, paddingTop: 10 }}>Total plan</td>
            <td /><td /><td style={{ ...td, paddingTop: 10 }}>100.0</td><td style={{ ...td, color: C.faint, paddingTop: 10 }}>100.0</td><td /><td />
            {periods.map((p, i) => <td key={p} style={{ ...ret(total[i]), paddingTop: 10, fontWeight: 600 }}>{sgn(total[i])}</td>)}
          </tr>
          {benchmark && (
            <Fragment>
              <tr>
                <td style={{ ...td, textAlign: "left", paddingLeft: 0, font: `13px ${F.body}`, color: C.mist }}>{performance.benchmarkLabel || "Policy benchmark"}</td>
                <td /><td /><td /><td /><td /><td />
                {periods.map((p, i) => <td key={p} style={{ ...td, color: C.mist }}>{sgn(benchmark[i])}</td>)}
              </tr>
              <tr>
                <td style={{ ...td, textAlign: "left", paddingLeft: 0, font: `13px ${F.body}`, color: C.faint }}>Excess</td>
                <td /><td /><td /><td /><td /><td />
                {periods.map((p, i) => {
                  const a = total[i], b = benchmark[i];
                  const e = isNum(a) && isNum(b) ? a - b : null;
                  return <td key={p} style={{ ...td, color: !isNum(e) ? C.faint : e < 0 ? C.warn : C.good }}>{sgn(e)}</td>;
                })}
              </tr>
            </Fragment>
          )}
        </tbody>
      </table>
      <div style={{ display: "flex", gap: 18, alignItems: "center", marginTop: 10, flexWrap: "wrap" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 5, font: `11px ${F.body}`, color: C.warn }}>
          <AlertFlag level="breach" dir={1} label="outside band" /> outside band
        </span>
        {wf !== null && (
          <span style={{ display: "flex", alignItems: "center", gap: 5, font: `11px ${F.body}`, color: C.amber }}>
            <AlertFlag level="watch" dir={1} label="approaching band" /> within the last {Math.round((1 - wf) * 100)}% of the band
          </span>
        )}
        <span style={{ font: `11px ${F.body}`, color: C.faint }}>Flag points up when above target, down when below.</span>
      </div>
      {performance.footnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 8 }}>{performance.footnote}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------- *
 *  LIQUIDITY TAB
 * ---------------------------------------------------------------- */

function CoverageBar({ current, worst, breach }: { current: number; worst: number | null; breach: number }) {
  // cov-01: unfunded / liquid against the 1.0 breach line (decision_metrics.py's
  // binding ratio; see the E1 measurement doc cited on liquidity.unfundedToLiquid).
  const max = Math.max(current, worst ?? 0, breach) * 1.15 || 1;
  const pc = (v: number) => `${(Math.max(0, Math.min(v, max)) / max) * 100}%`;
  const overBreach = current >= breach;
  return (
    <div>
      <div style={{ position: "relative", height: 16, background: C.well, border: `1px solid ${C.ruleSoft}` }}>
        <div style={{ position: "absolute", top: 3, bottom: 3, left: 0, width: pc(current), background: overBreach ? "rgba(217,112,90,0.62)" : "rgba(79,195,161,0.5)" }} />
        {isNum(worst) && (
          <div style={{ position: "absolute", top: -2, bottom: -2, left: pc(worst), width: 1, background: C.mist, opacity: 0.9 }} title={`worst so far: ${worst.toFixed(2)}`} />
        )}
        <div style={{ position: "absolute", top: -3, bottom: -3, left: pc(breach), width: 1, background: C.warn }} />
      </div>
      <div style={{ position: "relative", height: 14, marginTop: 3 }}>
        <span style={{ position: "absolute", left: 0, font: `10px ${F.mono}`, color: C.faint }}>0.0</span>
        <span style={{ position: "absolute", left: pc(breach), transform: "translateX(-50%)", font: `10px ${F.mono}`, color: C.warn }}>1.0 = breach</span>
        <span style={{ position: "absolute", right: 0, font: `10px ${F.mono}`, color: C.faint }}>{max.toFixed(1)}</span>
      </div>
    </div>
  );
}

function LiquidityTab() {
  const { liquidity, plan } = useView();
  const tiers = liquidity.tiers;
  const total = tiers.reduce((s, t) => s + t.value, 0) || 1;
  const f = liquidity.forecast12m;
  const flows = [
    { label: "Distributions", v: f.distributions },
    { label: "Investment income", v: f.income },
    { label: "Capital calls", v: isNum(f.calls) ? -f.calls : null },
    { label: liquidity.payoutLabel || "Benefit payments / spending", v: isNum(f.payout) ? -f.payout : null },
  ].filter((x): x is { label: string; v: number } => isNum(x.v));
  // fq=0 guard (carried from cio-01): an all-zero forecast12m means
  // forecast_quarters=0 — the payload has suppressed the forecast, and a
  // cover ratio against a zero outflow is a number that lies.
  const hasForecast = flows.some((x) => x.v !== 0);
  const net = isNum(f.net) ? f.net : flows.reduce((s, x) => s + x.v, 0);
  const outflow = Math.abs(net) || 1;
  const maxF = Math.max(...flows.map((x) => Math.abs(x.v)), 1);
  const liquid = tiers.filter((t) => t.liquid !== false).reduce((s, t) => s + t.value, 0);
  const defensive = tiers.filter((t) => t.tier === 1 || t.tier === 2).reduce((s, t) => s + t.value, 0);
  const t1 = tiers.find((t) => t.tier === 1);

  return (
    <Fragment>
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <Tile label="Tier 1 · cash" value={usd(t1 && t1.value)} sub={`${pct(((t1 ? t1.value : 0) / total) * 100)} of plan`}
          tone={t1 && t1.value / total < 0.02 ? C.warn : undefined} />
        <Tile label="Tiers 1–2 · defensive" value={usd(defensive)} sub={pct((defensive / total) * 100) + " of plan"} />
        <Tile label="Liquid, tiers 1–3" value={usd(liquid)} sub={pct((liquid / total) * 100) + " of plan"} />
        {hasForecast && (
          <Fragment>
            <Tile label="Net outflow, 12m" value={usd(net)} sub={pct((outflow / plan.totalValue) * 100) + " of plan"} tone={C.warn} />
            <Tile label="Cover of 12m outflow" value={`${(liquid / outflow).toFixed(1)}×`} sub={`tiers 1–2 alone: ${(defensive / outflow).toFixed(1)}×`} tone={C.good} />
          </Fragment>
        )}
        {isNum(liquidity.unfundedToNav) && (
          <Tile label="Unfunded ÷ private NAV" value={num(liquidity.unfundedToNav)}
            sub={isNum(liquidity.coverageAnchor) ? `${num(liquidity.coverageAnchor)} anchor` : undefined}
            tone={isNum(liquidity.coverageDanger) && liquidity.unfundedToNav > liquidity.coverageDanger ? C.warn : undefined} />
        )}
      </div>

      <Panel title="Liquidity tiers" note="by time to cash, without moving the market">
        <div style={{ display: "flex", height: 30, border: `1px solid ${C.rule}`, marginBottom: 16 }}>
          {tiers.map((t, i) => (
            <div key={t.id} style={{ width: `${(t.value / total) * 100}%`, background: t.colour || FALLBACK[i], opacity: 0.72, position: "relative" }}>
              {t.value / total > 0.06 && (
                <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", font: `600 12px ${F.mono}`, color: C.ink }}>
                  {pct((t.value / total) * 100)}
                </span>
              )}
            </div>
          ))}
        </div>

        <div style={{ display: "flex", font: `10px ${F.body}`, color: C.faint, letterSpacing: "0.1em", paddingBottom: 6 }}>
          <span style={{ width: 50 }}>TIER</span><span style={{ flex: 1 }}>DESCRIPTION</span>
          <span style={{ width: 90, textAlign: "right" }}>VALUE</span>
          <span style={{ width: 60, textAlign: "right" }}>SHARE</span>
          {/* fq=0 guard: this column is a ratio against the same suppressed
              outflow the tiles above are gated on — showing it here would
              print the same lying number in a quieter place. */}
          {hasForecast && <span style={{ width: 110, textAlign: "right" }}>COVER OF 12M OUTFLOW</span>}
        </div>
        {tiers.map((t, i) => (
          <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 9, padding: "9px 0", borderTop: `1px solid ${C.ruleSoft}` }}>
            <span style={{ width: 50, display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ width: 9, height: 9, background: t.colour || FALLBACK[i], display: "inline-block" }} />
              <span style={{ font: `11px ${F.mono}`, color: C.faint }}>{t.tier ? `T${t.tier}` : NA}</span>
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ font: `13px ${F.body}`, color: C.ice }}>{t.label}</div>
              <div style={{ font: `11px ${F.body}`, color: C.faint }}>{t.note}</div>
            </div>
            <span style={{ width: 90, textAlign: "right", font: `14px ${F.mono}`, color: C.ice }}>{usd(t.value)}</span>
            <span style={{ width: 60, textAlign: "right", font: `13px ${F.mono}`, color: C.faint }}>{pct((t.value / total) * 100)}</span>
            {hasForecast && (
              <span style={{ width: 110, textAlign: "right", font: `13px ${F.mono}`, color: C.mist }}>
                {t.liquid === false ? NA : `${(t.value / outflow).toFixed(1)}×`}
              </span>
            )}
          </div>
        ))}
        {liquidity.tierFootnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 10 }}>{liquidity.tierFootnote}</div>}
      </Panel>

      {isNum(liquidity.unfundedToLiquid) && (
        <Panel title="Coverage unfunded / liquid" style={{ marginTop: 10 }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
            <Tile label="Coverage now" value={num(liquidity.unfundedToLiquid)} sub="unfunded / liquid"
              tone={liquidity.unfundedToLiquid >= (liquidity.breachLine ?? 1.0) ? C.warn : undefined} />
            {isNum(liquidity.worstUnfundedToLiquid) && (
              <Tile label="Worst so far" value={num(liquidity.worstUnfundedToLiquid)} sub="running max, closed quarters"
                tone={liquidity.worstUnfundedToLiquid >= (liquidity.breachLine ?? 1.0) ? C.warn : undefined} />
            )}
          </div>
          <CoverageBar
            current={liquidity.unfundedToLiquid}
            worst={isNum(liquidity.worstUnfundedToLiquid) ? liquidity.worstUnfundedToLiquid : null}
            breach={isNum(liquidity.breachLine) ? liquidity.breachLine : 1.0}
          />
          <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 10, lineHeight: 1.5 }}>
            The line that moves with your commitments; 1.0 means unfunded commitments exceed liquid assets.
          </div>
        </Panel>
      )}

      {hasForecast && (
        <Panel title="Anticipated cashflows" note={`next twelve months · ${DENOMINATION_NOTE}`} style={{ marginTop: 10 }}>
          <div style={{ display: "flex", gap: 22, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 420px", minWidth: 340 }}>
              {flows.map((x) => (
                <div key={x.label} style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 0", borderBottom: `1px solid ${C.ruleSoft}` }}>
                  <span style={{ font: `13px ${F.body}`, color: C.mist, width: 190 }}>{x.label}</span>
                  <div style={{ flex: 1, height: 8, background: C.well, position: "relative", minWidth: 90 }}>
                    <div style={{
                      position: "absolute", top: 0, bottom: 0,
                      left: x.v >= 0 ? "50%" : `${50 - (Math.abs(x.v) / maxF) * 50}%`,
                      width: `${(Math.abs(x.v) / maxF) * 50}%`,
                      background: x.v >= 0 ? C.good : C.warn, opacity: 0.75,
                    }} />
                    <div style={{ position: "absolute", left: "50%", top: -3, bottom: -3, width: 1, background: C.rule }} />
                  </div>
                  <span style={{ font: `14px ${F.mono}`, color: x.v >= 0 ? C.good : C.warn, width: 72, textAlign: "right" }}>
                    {x.v >= 0 ? "+" : ""}{usd(x.v)}
                  </span>
                </div>
              ))}
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderTop: `1px solid ${C.rule}` }}>
                <span style={{ font: `600 13px ${F.body}`, color: C.ice, width: 190 }}>Net</span>
                <span style={{ flex: 1 }} />
                <span style={{ font: `600 16px ${F.mono}`, color: net < 0 ? C.warn : C.good, width: 72, textAlign: "right" }}>{usd(net)}</span>
              </div>
              {liquidity.flowFootnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 8, lineHeight: 1.5 }}>{liquidity.flowFootnote}</div>}
            </div>

            {liquidity.sourcing && liquidity.sourcing.length > 0 && (
              <div style={{ flex: "1 1 260px", minWidth: 250 }}>
                <div style={{ font: `10px ${F.body}`, letterSpacing: "0.12em", color: C.faint, textTransform: "uppercase", marginBottom: 8 }}>
                  Where the outflow is met
                </div>
                {liquidity.sourcing.map((s, i) => (
                  <div key={s.label} style={{ padding: "7px 0", borderBottom: `1px solid ${C.ruleSoft}` }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                      <span style={{ width: 8, height: 8, background: s.colour || FALLBACK[i], display: "inline-block" }} />
                      <span style={{ font: `13px ${F.body}`, color: C.mist }}>{s.label}</span>
                      <span style={{ marginLeft: "auto", font: `13px ${F.mono}`, color: s.value ? C.ice : C.faint }}>{usd(s.value)}</span>
                    </div>
                    <div style={{ height: 5, background: C.well, marginTop: 5, marginLeft: 16 }}>
                      <div style={{ height: "100%", width: `${(s.value / maxF) * 100}%`, background: s.colour || FALLBACK[i], opacity: 0.7 }} />
                    </div>
                  </div>
                ))}
                {liquidity.sourcingFootnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 10, lineHeight: 1.5 }}>{liquidity.sourcingFootnote}</div>}
              </div>
            )}
          </div>
        </Panel>
      )}
    </Fragment>
  );
}

/* ---------------------------------------------------------------- *
 *  PRIVATE CASHFLOWS TAB
 * ---------------------------------------------------------------- */

function CashflowBars({ rows, histCount }: { rows: PrivateQuarter[]; histCount: number }) {
  const W = 900, H = 250, L = 50, R = 20, T = 18, B = 30;
  const vals = rows.flatMap((r) => [r.distributions, -r.calls]);
  const hi = Math.max(...vals, 1) * 1.15, lo = Math.min(...vals, -1) * 1.15;
  const bw = (W - L - R) / rows.length;
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const zero = y(0), cut = L + bw * histCount;
  const step = Math.max(10, Math.round((hi - lo) / 5 / 10) * 10);
  const ticks: number[] = []; for (let v = Math.ceil(lo / step) * step; v < hi; v += step) ticks.push(v);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {histCount < rows.length && (
        <g>
          <rect x={cut} y={T} width={W - R - cut} height={H - T - B} fill={C.ice} opacity={0.03} />
          <text x={cut + 8} y={T + 12} fill={C.faint} style={{ font: `10px ${F.body}`, letterSpacing: "0.1em" }}>FORECAST · ROLL-FORWARD, NOT A PROJECTION</text>
        </g>
      )}
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={v === 0 ? C.rule : C.ruleSoft} />
          <text x={L - 8} y={y(v) + 3.5} textAnchor="end" fill={C.faint} style={{ font: `11px ${F.mono}` }}>{v}</text>
        </g>
      ))}
      {rows.map((r, i) => {
        const x0 = L + bw * i + bw * 0.16, w = bw * 0.68, op = r.forecast ? 0.42 : 0.85;
        return (
          <g key={r.label}>
            <rect x={x0} y={y(r.distributions)} width={w} height={Math.max(0, zero - y(r.distributions))} fill={C.good} opacity={op} />
            <rect x={x0} y={zero} width={w} height={Math.max(0, y(-r.calls) - zero)} fill={C.mist} opacity={op * 0.75} />
            {i % 2 === 0 && <text x={L + bw * (i + 0.5)} y={H - 10} textAnchor="middle" fill={C.faint} style={{ font: `10px ${F.body}` }}>{r.label}</text>}
          </g>
        );
      })}
      <path d={rows.map((r, i) => `${i ? "L" : "M"}${(L + bw * (i + 0.5)).toFixed(1)},${y(r.net).toFixed(1)}`).join(" ")} fill="none" stroke={C.amber} strokeWidth={2} />
      {rows.map((r, i) => <circle key={r.label} cx={L + bw * (i + 0.5)} cy={y(r.net)} r={1.8} fill={C.amber} opacity={r.forecast ? 0.5 : 1} />)}
    </svg>
  );
}

function RatioChart({
  rows,
  histCount,
  series,
  domain,
  title,
  anchor,
}: {
  rows: PrivateQuarter[];
  histCount: number;
  series: { label: string; c: string; get: (r: PrivateQuarter) => number | null }[];
  domain: [number, number];
  title: string;
  anchor?: number | null;
}) {
  const W = 440, H = 180, L = 44, R = 14, T = 26, B = 26;
  const bw = (W - L - R) / rows.length;
  // null (or otherwise non-finite) ratios are a real state — "denominator
  // was zero" — not zero itself. y() returns null for them so callers can
  // skip the point rather than coercing it through Number(null) -> 0 and
  // drawing a fabricated observation on the domain floor.
  const y = (v: number | null): number | null =>
    isNum(v) ? T + (1 - (v - domain[0]) / (domain[1] - domain[0])) * (H - T - B) : null;
  const cut = L + bw * histCount;
  const every = Math.ceil(rows.length / 5);
  // If every line in every series is null across every row, there is no
  // ratio data to plot at all: guard the panel with the empty state rather
  // than rendering axes over a blank chart (or, before this fix, an
  // Infinity/-Infinity domain feeding NaN into every coordinate).
  const anyFinite = series.some((s) => rows.some((r) => isNum(s.get(r))));
  if (!anyFinite) {
    return (
      <div style={{ flex: "1 1 340px", minWidth: 300 }}>
        <div style={{ font: `10px ${F.body}`, letterSpacing: "0.12em", color: C.faint, textTransform: "uppercase", marginBottom: 4 }}>{title}</div>
        <Empty what="ratio data" />
      </div>
    );
  }
  return (
    <div style={{ flex: "1 1 340px", minWidth: 300 }}>
      <div style={{ font: `10px ${F.body}`, letterSpacing: "0.12em", color: C.faint, textTransform: "uppercase", marginBottom: 4 }}>{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
        {histCount < rows.length && <rect x={cut} y={T} width={W - R - cut} height={H - T - B} fill={C.ice} opacity={0.03} />}
        {[domain[0], (domain[0] + domain[1]) / 2, domain[1]].map((v) => (
          <g key={v}>
            {/* domain bounds are always finite by construction (guarded at
                the call site), so y(v) is never null here */}
            <line x1={L} x2={W - R} y1={y(v)!} y2={y(v)!} stroke={C.ruleSoft} />
            <text x={L - 7} y={y(v)! + 3.5} textAnchor="end" fill={C.faint} style={{ font: `10px ${F.mono}` }}>{v.toFixed(2)}</text>
          </g>
        ))}
        {series.map((s) => {
          // Walk the row values and emit a moveto after every gap (a null
          // point) rather than coercing it into the line, so the line
          // breaks exactly where the data does — never a fabricated
          // observation on the domain floor.
          const segments: string[] = [];
          let pendingMove = true;
          for (let i = 0; i < rows.length; i++) {
            const py = y(s.get(rows[i]));
            if (py === null) { pendingMove = true; continue; }
            const px = L + bw * (i + 0.5);
            segments.push(`${pendingMove ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`);
            pendingMove = false;
          }
          // histCount === 0 (month 0, app-open-01/cio-05): there is no
          // closed row to mark as "as-of" — `rows[histCount - 1]` would be
          // `rows[-1]`, `undefined` in JS (not "the last element"), and
          // `s.get(undefined)` would throw reading a field off it.
          const markerY = histCount > 0 ? y(s.get(rows[histCount - 1])) : null;
          return (
            <g key={s.label}>
              <path d={segments.join(" ")} fill="none" stroke={s.c} strokeWidth={1.9} />
              {markerY !== null && <circle cx={L + bw * (histCount - 0.5)} cy={markerY} r={2.6} fill={s.c} />}
            </g>
          );
        })}
        {isNum(anchor) && anchor > domain[0] && anchor < domain[1] && (
          <g>
            <line x1={L} x2={W - R} y1={y(anchor)!} y2={y(anchor)!} stroke={C.warn} strokeDasharray="4 3" opacity={0.6} />
            <text x={W - R} y={y(anchor)! - 5} textAnchor="end" fill={C.warn} style={{ font: `10px ${F.body}` }}>{num(anchor)} anchor</text>
          </g>
        )}
        {rows.map((r, i) => (i % every === 0 ? (
          <text key={r.label} x={L + bw * (i + 0.5)} y={H - 8} textAnchor="middle" fill={C.faint} style={{ font: `10px ${F.body}` }}>{r.label}</text>
        ) : null))}
      </svg>
      <div style={{ marginTop: 2 }}><Legend items={series.map((s) => ({ label: s.label, c: s.c }))} /></div>
    </div>
  );
}

/** ER-6's terminal lapse (undrawn commitment cancelled, never called): a
 *  real value in the alert colour, a zero as a muted (never shouting)
 *  "$0m". DN-8 s3's `NA` ("—") means UNAVAILABLE — an unreached forecast
 *  quarter, a field the engine never tracked — and a known, tracked zero
 *  must not borrow that glyph: in a table where "—" already marks an
 *  unreached forecast column, a class that genuinely never lapsed would
 *  become indistinguishable from one where lapse isn't tracked at all
 *  (M-1). Missing (`null`/`undefined`) still renders `NA`; only a known
 *  zero moved off it. `lapse-value` className is a stable test hook
 *  (CioDashboard.test.tsx's zero-lapse assertion targets it, since the
 *  surrounding table has plenty of legitimate "$0m" cells in unrelated
 *  columns). */
function lapseCell(v: number | null | undefined) {
  if (!isNum(v)) return <span className="lapse-value" style={{ color: C.faint }}>{NA}</span>;
  if (v <= 0) return <span className="lapse-value" style={{ color: C.faint }}>{usd(0)}</span>;
  return <span className="lapse-value" style={{ color: C.warn }}>{usd(v)}</span>;
}

/** The programme's cohort NAV stack at the as-of quarter, oldest vintage
 *  first — the successor to the retired PrivateMarkets.ladderSummary
 *  (cio-03b). Context, not a headline: kept small and unlabelled per bar,
 *  with the id/NAV in a title and a class-level legend below. */
function VintageLadder({
  vintages,
  classes,
}: {
  vintages: VintageRung[];
  classes: { id: string; label: string }[];
}) {
  const total = vintages.reduce((s, v) => s + v.navTrue, 0);
  const colourOf = (assetId: string) => {
    const i = classes.findIndex((c) => c.id === assetId);
    return FALLBACK[(i < 0 ? 0 : i) % FALLBACK.length];
  };
  return (
    <div>
      <div
        style={{
          display: "flex",
          height: 14,
          width: "100%",
          borderRadius: 2,
          overflow: "hidden",
          border: `1px solid ${C.rule}`,
        }}
      >
        {vintages.map((v) => {
          const asset = v.id.split("-")[0];
          const w = total > 0 ? Math.max(0.4, (v.navTrue / total) * 100) : 100 / vintages.length;
          return (
            <div
              key={v.id}
              className="vintage-rung"
              title={`${v.label}: ${usd(v.navTrue)}`}
              style={{ width: `${w}%`, background: colourOf(asset), opacity: 0.78 }}
            />
          );
        })}
      </div>
      <div style={{ marginTop: 6 }}>
        <Legend items={classes.map((c, i) => ({ label: c.label, c: FALLBACK[i % FALLBACK.length] }))} />
      </div>
    </div>
  );
}

function PrivateTab() {
  const { privateCashflows: pcf, plan, liquidity } = useView();
  const [sel, setSel] = useState<string>("aggregate");
  if (!pcf || !pcf.series) return <Empty what="private cashflow series" />;

  const options: { id: string; label: string }[] = [{ id: "aggregate", label: pcf.aggregateLabel || "Aggregate" }].concat(pcf.classes);
  const rows = pcf.series[sel] || pcf.series.aggregate;
  // app-open-01 (cio-05): the month-0 CIO view can legitimately serve zero
  // rows (histCount 0 AND forecast_quarters 0 both requested) — nothing to
  // plot at all, honestly, rather than a crash.
  if (rows.length === 0) return <Empty what="private cashflow history — advance past the opening quarter" />;
  const H = pcf.histCount;
  // month 0 (H === 0): nothing has CLOSED yet, so `rows[H - 1]` (JS: -1 is
  // not "the last element", it's `undefined`) would both crash and, if it
  // didn't, misname the FIRST FORECAST row's mechanically-projected
  // navClose/unfundedClose as "now". The real "now" at H === 0 is the
  // entered opening book itself — rows[0].navOpen/.unfundedOpen ARE that
  // (cioview.py's row() reads them straight off active.opening for i===0),
  // so `opened` routes the static tiles there and nulls the flow-rate ones
  // (calls÷unfunded, calls÷NAV): those describe something that happened
  // OVER a quarter, and no quarter — real or forecast — represents "now".
  const opened = H === 0;
  const cur = rows[Math.max(0, H - 1)];
  const navNow = opened ? cur.navOpen : cur.navClose;
  const unfundedNow = opened ? cur.unfundedOpen : cur.unfundedClose;
  const coverageNow = opened ? (navNow > 0 ? unfundedNow / navNow : null) : cur.coverage;
  const callRateUnfundedNow = opened ? null : cur.callRateUnfunded;
  const callRateNavNow = opened ? null : cur.callRateNav;
  const expiredNow = opened ? 0 : cur.expiredUndrawn;
  const sum = (a: PrivateQuarter[], k: "calls" | "distributions" | "net") => a.reduce((s, r) => s + (r[k] || 0), 0);
  const ltm = rows.slice(Math.max(0, H - 4), H);
  const fwd = rows.slice(H, H + 4);
  // ER-6's terminal lapse: undrawn commitment cancelled at the end of a
  // cohort's life. Real but rare — an LTM window mostly reads zero, so this
  // sums the FULL realised history, not just the trailing four quarters.
  const lapsedToDate = rows.slice(0, H).reduce((s, r) => s + (r.expiredUndrawn || 0), 0);
  const anchor = liquidity && liquidity.coverageAnchor;
  const danger = liquidity && liquidity.coverageDanger;

  // Two ways a domain can stop being a domain, both of which RatioChart's
  // y() turns into NaN (division by a zero span): an empty input array
  // (Math.min/max of [] -> Infinity/-Infinity), and a *nonempty* one that's
  // uniformly a single finite value (e.g. every present call rate reading
  // exactly 0 - real and reachable per cioview.py's callRateNav = calls /
  // navOpen) collapsing hi === lo. Both are guarded here so the domains
  // handed to RatioChart are always finite AND have a nonzero span.
  const finiteSpan = (lo: number, hi: number): [number, number] =>
    hi > lo ? [lo, hi] : [lo, lo + 1];
  const covVals = rows.map((r) => r.coverage).filter(isNum);
  const covDom: [number, number] = covVals.length
    ? finiteSpan(Math.max(0, Math.min(...covVals) - 0.1), Math.max(...covVals) + 0.1)
    : [0, 1];
  const rateVals = rows.flatMap((r) => [r.callRateUnfunded, r.callRateNav]).filter(isNum);
  const rateDom: [number, number] = rateVals.length
    ? finiteSpan(0, Math.max(...rateVals) * 1.25)
    : [0, 1];

  return (
    <Fragment>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
        {options.map((o) => (
          <button key={o.id} onClick={() => setSel(o.id)} style={{
            padding: "6px 13px", cursor: "pointer", borderRadius: 2, font: `13px ${F.body}`,
            border: `1px solid ${sel === o.id ? C.ice : C.rule}`,
            background: sel === o.id ? C.ice : "transparent", color: sel === o.id ? C.ink : C.mist,
          }}>{o.label}</button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <Tile label={opened ? "NAV (opening)" : "NAV"} value={usd(navNow)} sub={`${pct((navNow / plan.totalValue) * 100)} of plan`} />
        <Tile label={opened ? "Unfunded (opening)" : "Unfunded"} value={usd(unfundedNow)} />
        <Tile label="Unfunded ÷ NAV" value={num(coverageNow)} sub={isNum(anchor) ? `${num(anchor)} anchor` : undefined}
          tone={isNum(danger) && Number(coverageNow) > danger ? C.warn : undefined} />
        <Tile label="Calls ÷ unfunded" value={pct(isNum(callRateUnfundedNow) ? callRateUnfundedNow * 100 : null)} sub="quarterly call rate" />
        <Tile label="Calls ÷ NAV" value={pct(isNum(callRateNavNow) ? callRateNavNow * 100 : null)} sub="quarterly" />
        <Tile label="Net cashflow, LTM" value={usd(sum(ltm, "net"))} tone={sum(ltm, "net") < 0 ? C.warn : C.good}
          sub={fwd.length ? `next 4q: ${usd(sum(fwd, "net"))}` : undefined} />
        {/* F2's closure required both halves: the release in the quarter it
            happens AND the running total afterwards. `lapsedToDate` gives the
            second; without the first, a monotonically-rising cumulative never
            says which quarter moved — and post-ER-12 the lapse is ~0.47-0.49
            a year spread across many quarters, not one large event, so that
            distinction is the whole point (I-2). `expiredNow` is the as-of
            quarter's own figure, real zero when nothing has closed yet. */}
        <Tile label="Lapsed to date" value={lapsedToDate > 0 ? usd(lapsedToDate) : NA}
          tone={lapsedToDate > 0 ? C.warn : undefined}
          sub={isNum(expiredNow) && expiredNow > 0
            ? `${usd(expiredNow)} this quarter · ER-6`
            : "ER-6: undrawn commitment released, never called"} />
      </div>

      <Panel title="Capital calls, distributions and net"
        note={`${DENOMINATION_NOTE} per quarter · ${H} realised, ${rows.length - H} forecast`}
        right={<Legend items={[{ label: "Distributions", c: C.good, w: 8 }, { label: "Calls", c: C.mist, w: 8 }, { label: "Net", c: C.amber }]} />}>
        <CashflowBars rows={rows} histCount={H} />
      </Panel>

      <Panel title="Ratios" note="shaded region is forecast" style={{ marginTop: 10 }}>
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          <RatioChart rows={rows} histCount={H} title="Call rates" domain={rateDom}
            series={[
              { label: "Calls ÷ opening unfunded", c: C.amber, get: (r) => r.callRateUnfunded },
              { label: "Calls ÷ opening NAV", c: C.blue, get: (r) => r.callRateNav },
            ]} />
          <RatioChart rows={rows} histCount={H} title="Unfunded commitment ÷ NAV" domain={covDom} anchor={anchor}
            series={[{ label: "Coverage", c: C.good, get: (r) => r.coverage }]} />
        </div>
      </Panel>

      <Panel title="By asset class" note="last twelve months · forecast next four quarters" style={{ marginTop: 10 }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 780 }}>
            <thead>
              <tr>
                {["Asset class", "NAV", "Unfunded", "Unf ÷ NAV", "Calls LTM", "Dists LTM", "Net LTM", "Call rate", "Lapsed to date", "Net next 4q"].map((h, i) => (
                  <th key={h} style={{ font: `10px ${F.body}`, letterSpacing: "0.1em", color: C.faint, textTransform: "uppercase", padding: "0 8px 7px", textAlign: i ? "right" : "left" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pcf.classes.concat([{ id: "aggregate", label: pcf.aggregateLabel || "Aggregate" }]).map((cl) => {
                const rs = pcf.series[cl.id]; if (!rs) return null;
                const h = rs.slice(Math.max(0, H - 4), H), fw = rs.slice(H, H + 4);
                // month 0 (H === 0): same reasoning as the tiles above — the
                // real "now" is the opening book, not the first forecast
                // row's projected close, and no quarter's calls have landed.
                const c = rs[Math.max(0, H - 1)];
                const rowNav = H > 0 ? c.navClose : c.navOpen;
                const rowUnfunded = H > 0 ? c.unfundedClose : c.unfundedOpen;
                const rowCoverage = H > 0 ? c.coverage : (rowNav > 0 ? rowUnfunded / rowNav : null);
                const rowCallRate = H > 0 ? c.callRateUnfunded : null;
                const s = (a: PrivateQuarter[], k: "calls" | "distributions" | "net") => a.reduce((x, r) => x + (r[k] || 0), 0);
                const lapsed = rs.slice(0, H).reduce((x, r) => x + (r.expiredUndrawn || 0), 0);
                const agg = cl.id === "aggregate";
                const td: React.CSSProperties = { font: `13px ${F.mono}`, color: C.ice, padding: "6px 8px", textAlign: "right" };
                return (
                  <tr key={cl.id} onClick={() => setSel(cl.id)} style={{ borderTop: `1px solid ${agg ? C.rule : C.ruleSoft}`, cursor: "pointer" }}>
                    <td style={{ ...td, textAlign: "left", font: `${agg ? 600 : 400} 13px ${F.body}`, color: sel === cl.id ? C.amber : C.mist }}>{cl.label}</td>
                    <td style={td}>{usd(rowNav)}</td>
                    <td style={td}>{usd(rowUnfunded)}</td>
                    <td style={{ ...td, color: isNum(danger) && Number(rowCoverage) > danger ? C.warn : C.ice }}>{num(rowCoverage)}</td>
                    <td style={td}>{usd(s(h, "calls"))}</td>
                    <td style={td}>{usd(s(h, "distributions"))}</td>
                    <td style={{ ...td, color: s(h, "net") < 0 ? C.warn : C.good }}>{usd(s(h, "net"))}</td>
                    <td style={{ ...td, color: C.mist }}>{pct(isNum(rowCallRate) ? rowCallRate * 100 : null)}</td>
                    <td style={td}>{lapseCell(lapsed)}</td>
                    <td style={{ ...td, color: s(fw, "net") < 0 ? C.warn : C.good }}>{fw.length ? usd(s(fw, "net")) : NA}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {pcf.footnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 8 }}>{pcf.footnote}</div>}
      </Panel>

      {pcf.vintages && pcf.vintages.length > 0 && (
        <Panel title="Vintage ladder" note="as-of quarter · true NAV · oldest first" style={{ marginTop: 10 }}>
          <VintageLadder vintages={pcf.vintages} classes={pcf.classes} />
        </Panel>
      )}
    </Fragment>
  );
}

/* ---------------------------------------------------------------- *
 *  MARKETS TAB
 * ---------------------------------------------------------------- */

function SeriesChart({ s, indexed, height }: { s: MarketSeries; indexed: boolean; height: number }) {
  const W = 420, H = height, T = 12, B = 24, L = 40, R = 40;
  const N = s.path.length - 1;
  const lo = Math.min(...s.path) * (indexed ? 0.97 : 0.9), hi = Math.max(...s.path) * (indexed ? 1.03 : 1.08);
  const x = (m: number) => L + (m / N) * (W - L - R);
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const d = s.path.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = s.path[N], dp = s.dp == null ? 0 : s.dp;
  const gid = `g-${s.id}`;
  const xTicks: number[] = []; for (let m = N; m >= 0; m -= 12) xTicks.unshift(m);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={s.colour} stopOpacity="0.20" /><stop offset="100%" stopColor={s.colour} stopOpacity="0.01" />
        </linearGradient>
      </defs>
      {[0.15, 0.55, 0.92].map((f) => {
        const v = lo + (hi - lo) * f;
        return (
          <g key={f}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={C.ruleSoft} />
            <text x={L - 7} y={y(v) + 3.5} textAnchor="end" fill={C.faint} style={{ font: `10px ${F.mono}` }}>{v.toFixed(dp)}</text>
          </g>
        );
      })}
      {indexed && <line x1={L} x2={W - R} y1={y(100)} y2={y(100)} stroke={C.rule} strokeDasharray="3 3" />}
      <path d={`${d} L${x(N)},${y(lo)} L${x(0)},${y(lo)} Z`} fill={`url(#${gid})`} />
      <path d={d} fill="none" stroke={s.colour} strokeWidth={1.9} />
      <circle cx={x(N)} cy={y(last)} r={3} fill={s.colour} />
      <text x={x(N) + 7} y={y(last) + 4} fill={s.colour} style={{ font: `12px ${F.mono}` }}>{last.toFixed(dp)}</text>
      {xTicks.map((m) => (
        <text key={m} x={x(m)} y={H - 7} textAnchor="middle" fill={C.faint} style={{ font: `10px ${F.body}` }}>
          {m === N ? "now" : `−${((N - m) / 12).toFixed(0)}y`}
        </text>
      ))}
    </svg>
  );
}

function MarketCard({
  s,
  periods,
  indexed = true,
  height = 150,
}: {
  s: MarketSeries;
  periods?: string[];
  indexed?: boolean;
  height?: number;
}) {
  const N = s.path.length - 1;
  const last = s.path[N];
  const chg = indexed ? (last / s.path[0] - 1) * 100 : last - s.path[0];
  const returns = s.returns;
  return (
    <div style={{ flex: "1 1 300px", minWidth: 280, background: C.well, border: `1px solid ${C.rule}`, padding: "12px 14px 8px" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 2 }}>
        <span style={{ font: `14px ${F.body}`, color: C.ice }}>{s.label}</span>
        <span style={{ marginLeft: "auto", font: `14px ${F.mono}`, color: chg >= 0 ? C.good : C.warn }}>
          {sgn(chg, s.dp == null ? 1 : s.dp)}{indexed ? "%" : ` ${s.unit || ""}`}
        </span>
        <span style={{ font: `10px ${F.body}`, color: C.faint, letterSpacing: "0.08em" }}>{Math.round(N / 12)}Y</span>
      </div>
      <SeriesChart s={s} indexed={indexed} height={height} />
      {returns && periods && (
        <div style={{ display: "flex", borderTop: `1px solid ${C.ruleSoft}`, marginTop: 6, paddingTop: 6 }}>
          {periods.map((p, i) => {
            const v = returns[i];
            return (
              <div key={p} style={{ flex: 1, textAlign: "center" }}>
                <div style={{ font: `9px ${F.body}`, color: C.faint, letterSpacing: "0.08em" }}>{p}</div>
                <div style={{ font: `12px ${F.mono}`, color: !isNum(v) ? C.faint : v < 0 ? C.warn : C.ice }}>{sgn(v)}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function MarketsTab() {
  const { markets, performance } = useView();
  if (!markets) return <Empty what="market series" />;
  return (
    <Fragment>
      {markets.tiles && markets.tiles.length > 0 && (
        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          {markets.tiles.map((t) => <Tile key={t.label} label={t.label} value={t.value} sub={t.sub} tone={t.tone === "warn" ? C.warn : undefined} />)}
        </div>
      )}

      {markets.returns && markets.returns.length > 0 && (
        <Panel title="Returns" note="indexed to 100 at the start of the window · period returns beneath each chart">
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {markets.returns.map((s) => <MarketCard key={s.id} s={s} periods={performance.periods} />)}
          </div>
          {markets.returnsFootnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 8 }}>{markets.returnsFootnote}</div>}
        </Panel>
      )}

      {markets.conditions && markets.conditions.length > 0 && (
        <Panel title="Conditions" note="the macro state the world is generating" style={{ marginTop: 10 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {markets.conditions.map((s) => <MarketCard key={s.id} s={s} indexed={false} height={140} />)}
          </div>
          {markets.conditionsFootnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 8 }}>{markets.conditionsFootnote}</div>}
        </Panel>
      )}

      {markets.correlations && markets.correlations.length > 0 && (
        <Panel title="Correlation" note={markets.correlationNote || "rolling window, against the growth benchmark"} style={{ marginTop: 10 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {markets.correlations.map((r, i) => (
              <div key={r.id || i} style={{ flex: "1 1 160px", minWidth: 150, background: C.well, border: `1px solid ${C.rule}`, padding: "10px 12px" }}>
                <div style={{ font: `12px ${F.body}`, color: C.mist }}>{r.label}</div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 3 }}>
                  <span style={{ font: `600 20px ${F.mono}`, color: C.ice }}>{num(r.current)}</span>
                  <span style={{ font: `12px ${F.mono}`, color: r.current - r.baseline > 0.1 ? C.warn : C.faint }}>{sgn(r.current - r.baseline, 2)} vs avg</span>
                </div>
                <div style={{ position: "relative", height: 5, background: C.ink, marginTop: 7 }}>
                  <div style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: C.rule }} />
                  <div style={{
                    position: "absolute", top: 0, bottom: 0,
                    left: r.current >= 0 ? "50%" : `${50 + r.current * 50}%`,
                    width: `${Math.abs(r.current) * 50}%`,
                    background: r.current >= 0 ? C.warn : C.blue, opacity: 0.7,
                  }} />
                </div>
              </div>
            ))}
          </div>
          {markets.correlationFootnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 8 }}>{markets.correlationFootnote}</div>}
        </Panel>
      )}
    </Fragment>
  );
}

/* ---------------------------------------------------------------- *
 *  SHELL
 * ---------------------------------------------------------------- */

type TabKey = "plan" | "liquidity" | "private" | "markets";
const TABS: [TabKey, string][] = [
  ["plan", "Plan"], ["liquidity", "Liquidity"],
  ["private", "Private cashflows"], ["markets", "Markets"],
];

export interface ExtraTab {
  key: string;
  label: string;
  /** Host-owned content. Called only while its tab is selected. */
  render: () => ReactNode;
}

export default function CioDashboard({
  view,
  onPlaneChange,
  initialTab = "plan",
  chrome = "full",
  extraTabs = [],
}: {
  view: CioView;
  onPlaneChange: (p: Plane) => void;
  initialTab?: TabKey;
  /** "embedded": the host owns the plane control and the footer (cockpit). */
  chrome?: "full" | "embedded";
  extraTabs?: ExtraTab[];
}) {
  const [tab, setTab] = useState<string>(initialTab);
  const { meta, plan } = view;
  const planes = meta.planesAvailable ?? ["reported"];
  const allTabs = [...TABS, ...extraTabs.map((t) => [t.key, t.label] as const)];

  return (
    <ViewCtx.Provider value={view}>
      {/* full chrome's outer padding and the inner 1220px document width are
          both inline styles, which no stylesheet selector (short of
          !important) can override for an embedded host — see cio-03 task 2
          report. Embedded (the cockpit) computes its own values here instead
          of fighting the inline style from outside. */}
      <div className={`ciodash${chrome === "embedded" ? " ciodash-embedded" : ""}`} style={{ padding: chrome === "embedded" ? "12px 16px 20px" : "18px 20px 40px", color: C.ice, font: `14px ${F.body}` }}>
        <div style={{ maxWidth: chrome === "embedded" ? undefined : 1220, margin: "0 auto" }}>
          <header style={{ display: "flex", alignItems: "flex-end", gap: 20, flexWrap: "wrap", paddingBottom: 12 }}>
            <div>
              <div style={{ font: `10px ${F.body}`, letterSpacing: "0.22em", color: C.faint }}>TERRARIUM · CIO DASHBOARD</div>
              <h1 style={{ font: `400 29px ${F.display}`, margin: "4px 0 0" }}>{meta.worldTitle}</h1>
            </div>
            {/* meta.asOfMonth is the 0-based index of the last revealed month, not a count */}
            <div style={{ font: `12px ${F.mono}`, color: C.faint, paddingBottom: 4 }}>
              seed {meta.seed} · {meta.asOfLabel} · linkage {meta.linkageVersion}
            </div>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14, paddingBottom: 2 }}>
              {meta.regime && <span style={{ font: `12px ${F.body}`, color: C.warn, letterSpacing: "0.1em" }}>REGIME · {meta.regime.toUpperCase()}</span>}
              {chrome !== "embedded" && planes.length > 1 && (
                <div className="ciodash-planes" style={{ display: "flex", border: `1px solid ${C.rule}`, borderRadius: 2, overflow: "hidden" }}>
                  {planes.map((k) => (
                    <button key={k} onClick={() => onPlaneChange(k)} style={{
                      padding: "6px 14px", cursor: "pointer", border: "none", font: `13px ${F.body}`,
                      background: meta.plane === k ? C.ice : "transparent", color: meta.plane === k ? C.ink : C.mist,
                    }}>{k === "true" ? "True" : "Reported"}</button>
                  ))}
                </div>
              )}
            </div>
          </header>

          <nav style={{ display: "flex", gap: 26, borderBottom: `1px solid ${C.rule}`, marginBottom: 12 }}>
            {allTabs.map(([k, l]) => (
              <button key={k} onClick={() => setTab(k)} style={{
                background: "none", border: "none", cursor: "pointer", padding: "0 0 9px",
                font: `${tab === k ? 600 : 400} 15px ${F.body}`, color: tab === k ? C.ice : C.faint,
                borderBottom: `2px solid ${tab === k ? C.amber : "transparent"}`, marginBottom: -1,
              }}>{l}</button>
            ))}
          </nav>

          {tab === "plan" && (
            <Fragment>
              {/* app-open-01 item 2: plan growth and asset allocation sit
                  side by side, each half width — .cio-plan-row (styles.css)
                  follows the app's existing minmax-grid idiom (.chart-grid)
                  and stacks on its own below the same width a single panel
                  would otherwise get uncomfortably narrow, no separate
                  media query needed. */}
              <div className="cio-plan-row">
                <Panel title="Plan growth" note={`${plan.windowLabel || "five years"} · ${DENOMINATION_NOTE}`}
                  right={
                    <div style={{ display: "flex", gap: 16, font: `12px ${F.body}`, color: C.faint }}>
                      {/* app-open-01 item 1: same headline figure as the
                          donut center, same usd() rendering. */}
                      <span>Now <b style={{ color: C.ice, font: `13px ${F.mono}` }}>{usd(plan.totalValue)}</b></span>
                      {isNum(plan.growthPct) && <span>Growth <b style={{ color: plan.growthPct >= 0 ? C.good : C.warn, font: `13px ${F.mono}` }}>{sgn(plan.growthPct)}%</b></span>}
                      {isNum(plan.netOfFlows) && <span>Net of flows <b style={{ color: C.ice, font: `13px ${F.mono}` }}>{usd(plan.netOfFlows)}</b></span>}
                    </div>
                  }>
                  <PlanGrowth />
                </Panel>

                <Panel title="Asset allocation" note="by goal · current weights"
                  right={<AlertSummary counts={allocationAlerts(view.allocation)} />}>
                  <AllocationDonut />
                </Panel>
              </div>

              <Panel title="Performance and allocation" note={meta.plane === "true" ? "true plane" : "reported plane"} style={{ marginTop: 10 }}
                right={<AlertSummary counts={allocationAlerts(view.allocation)} />}>
                <PerfTable />
              </Panel>
            </Fragment>
          )}

          {tab === "liquidity" && <LiquidityTab />}
          {tab === "private" && <PrivateTab />}
          {tab === "markets" && <MarketsTab />}

          {extraTabs.map((t) => (tab === t.key ? <Fragment key={t.key}>{t.render()}</Fragment> : null))}

          {chrome !== "embedded" && (
            <footer className="ciodash-footer" style={{ marginTop: 18, paddingTop: 12, borderTop: `1px solid ${C.ruleSoft}`, font: `11px ${F.body}`, color: C.faint, display: "flex", gap: 18, flexWrap: "wrap" }}>
              <span style={{ letterSpacing: "0.14em" }}>{meta.watermark || "SIMULATED WORLD — NOT A FORECAST"}</span>
              <span>{meta.disclaimer}</span>
              <span style={{ marginLeft: "auto", font: `11px ${F.mono}` }}>run {meta.runId} · replayable from RunRecord</span>
            </footer>
          )}
        </div>
      </div>
    </ViewCtx.Provider>
  );
}
