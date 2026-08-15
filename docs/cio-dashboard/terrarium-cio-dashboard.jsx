import { useState, useMemo, useContext, createContext, Fragment } from "react";

/* ==================================================================
 *  TERRARIUM — CIO DASHBOARD  ·  v0.3
 *
 *  This component is a PURE RENDERER. It computes nothing that is
 *  scoreable, disclosed, or governed. Everything it draws arrives in
 *  a single `view` payload conforming to CioView (see cioView.ts and
 *  DN-8 for the contract).
 *
 *  To wire up:
 *    1. Implement buildCioView(runRecord, { plane, asOf }) engine-side.
 *    2. Pass it in:  <CIODashboard view={v} onPlaneChange={setPlane} />
 *    3. Delete the MOCK DATA block at the foot of this file.
 *
 *  Contract summary — DN-8 §3 has the full field list:
 *    · percentages are numbers in percentage points (26.1, not 0.261)
 *    · money is in the unit named by meta.unitLabel (default $m)
 *    · calls, distributions and payout are POSITIVE MAGNITUDES; the
 *      renderer applies sign. net = distributions − calls.
 *    · any period the run has not reached must be null, never 0.
 *    · every forecast row carries forecast: true and is a mechanical
 *      roll-forward, not a projection. The renderer labels it as such
 *      and that label is not optional.
 * ================================================================== */

/* ---------------------------------------------------------------- *
 *  THEME
 * ---------------------------------------------------------------- */

const C = {
  ink: "#0B1220", panel: "#111B2C", well: "#0D1524",
  rule: "#21304A", ruleSoft: "#18243A",
  ice: "#E6EDF8", mist: "#8FA2BE", faint: "#5B6E8E",
  warn: "#D9705A", good: "#58B49E", amber: "#F0C46A", blue: "#6E9BD1",
};

const F = {
  display: 'Cambria, "Palatino Linotype", Georgia, serif',
  body: 'Calibri, "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif',
  mono: 'Consolas, "SF Mono", "Cascadia Mono", ui-monospace, monospace',
};

const GOAL_COLOUR = { growth: "#F0C46A", real: "#58B49E", income: "#6E9BD1", diversifier: "#A88BC4" };
const FALLBACK = ["#F0C46A", "#58B49E", "#6E9BD1", "#A88BC4", "#D9705A", "#8FA2BE"];
const goalColour = (id, i) => GOAL_COLOUR[id] || FALLBACK[i % FALLBACK.length];

/* ---------------------------------------------------------------- *
 *  FORMATTING — the only place units become strings
 * ---------------------------------------------------------------- */

const NA = "—";
const isNum = (v) => typeof v === "number" && Number.isFinite(v);

const money = (v, unit = "m") => {
  if (!isNum(v)) return NA;
  const s = v < 0 ? "−" : "";
  const a = Math.abs(v);
  return unit === "m" && a >= 1000 ? `${s}$${(a / 1000).toFixed(2)}bn` : `${s}$${Math.round(a)}${unit}`;
};
const pct = (v, d = 1) => (isNum(v) ? `${v.toFixed(d)}%` : NA);
const sgn = (v, d = 1) => (isNum(v) ? (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d) : NA);
const num = (v, d = 2) => (isNum(v) ? v.toFixed(d) : NA);

/* ---------------------------------------------------------------- *
 *  ALERTS
 *  Levels come from the engine when supplied (class.alert / goal.alert).
 *  Fallback: "breach" is |dev| > band, which needs no parameter.
 *  "watch" needs a threshold, so it renders ONLY when the payload
 *  supplies allocation.alertPolicy.watchFraction. The renderer does
 *  not carry a default — see DN-8 §7.
 * ---------------------------------------------------------------- */

const ALERT_COLOUR = { breach: C.warn, watch: C.amber, ok: null };

function alertLevel(cur, target, band, policy, explicit) {
  if (explicit) return explicit;
  if (!isNum(cur) || !isNum(target) || !isNum(band) || band <= 0) return "ok";
  const d = Math.abs(cur - target);
  if (d > band) return "breach";
  const wf = policy && isNum(policy.watchFraction) ? policy.watchFraction : null;
  if (wf !== null && d >= wf * band) return "watch";
  return "ok";
}

function AlertFlag({ level, dir, label }) {
  if (!level || level === "ok") return <span style={{ display: "inline-block", width: 15 }} />;
  const c = ALERT_COLOUR[level];
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

function allocationAlerts(allocation) {
  const policy = allocation.alertPolicy;
  let breach = 0, watch = 0;
  allocation.classes.forEach((c) => {
    const l = alertLevel(c.currentPct, c.targetPct, c.bandPct, policy, c.alert);
    if (l === "breach") breach++; else if (l === "watch") watch++;
  });
  return { breach, watch, policy };
}

function AlertSummary({ counts }) {
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

const ViewCtx = createContext(null);
const useView = () => useContext(ViewCtx);

/* ---------------------------------------------------------------- *
 *  PRIMITIVES
 * ---------------------------------------------------------------- */

function Panel({ title, note, right, children, style }) {
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

function Tile({ label, value, sub, tone }) {
  return (
    <div style={{ flex: "1 1 150px", minWidth: 140, padding: "11px 13px", background: C.well, border: `1px solid ${C.rule}` }}>
      <div style={{ font: `10px ${F.body}`, letterSpacing: "0.12em", color: C.faint, textTransform: "uppercase" }}>{label}</div>
      <div style={{ font: `600 22px ${F.mono}`, color: tone || C.ice, marginTop: 4, lineHeight: 1.1 }}>{value}</div>
      {sub && <div style={{ font: `12px ${F.body}`, color: C.faint, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function Legend({ items }) {
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

function Empty({ what }) {
  return <div style={{ padding: "22px 0", font: `13px ${F.body}`, color: C.faint, textAlign: "center" }}>No {what} in this payload.</div>;
}

/* ---------------------------------------------------------------- *
 *  PLAN — growth
 * ---------------------------------------------------------------- */

function PlanGrowth() {
  const { plan, meta } = useView();
  const p = plan.history;
  if (!p || !p.values || !p.values.length) return <Empty what="plan history" />;

  const N = p.values.length - 1;
  const START = Math.max(0, Math.min(p.worldStartIndex == null ? 0 : p.worldStartIndex, N));
  const W = 900, H = 230, L = 56, R = 16, T = 22, B = 26;
  const vals = p.values.filter(isNum);
  const pad = (Math.max(...vals) - Math.min(...vals)) * 0.18 || 1;
  const lo = Math.min(...vals) - pad, hi = Math.max(...vals) + pad;
  const x = (m) => L + (m / N) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const seg = (a, b) => p.values.slice(a, b + 1).map((v, i) => `${i ? "L" : "M"}${x(a + i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const pre = seg(0, START), post = seg(START, N);
  const xTicks = []; for (let m = N; m >= 0; m -= 12) xTicks.unshift(m);

  return (
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
  );
}

/* ---------------------------------------------------------------- *
 *  PLAN — allocation donut
 * ---------------------------------------------------------------- */

function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const m = (v) => Math.round(f < 0 ? v * (1 + f) : v + (255 - v) * f);
  return `rgb(${m(r)},${m(g)},${m(b)})`;
}
function arcPath(cx, cy, r0, r1, a0, a1) {
  const rad = (a) => ((a - 90) * Math.PI) / 180;
  const p = (r, a) => [cx + r * Math.cos(rad(a)), cy + r * Math.sin(rad(a))];
  const big = a1 - a0 > 180 ? 1 : 0;
  const [x0, y0] = p(r1, a0), [x1, y1] = p(r1, a1), [x2, y2] = p(r0, a1), [x3, y3] = p(r0, a0);
  return `M${x0},${y0} A${r1},${r1} 0 ${big} 1 ${x1},${y1} L${x2},${y2} A${r0},${r0} 0 ${big} 0 ${x3},${y3} Z`;
}

function AllocationDonut() {
  const { allocation, plan, meta } = useView();
  const policy = allocation.alertPolicy;
  const wf = policy && isNum(policy.watchFraction) ? policy.watchFraction : null;
  const W = 560, H = 420, cx = 268, cy = 208;
  const R_IN0 = 78, R_IN1 = 112, R_OUT0 = 116, R_OUT1 = 148, LABEL_X = 196, GAP = 27;

  const rings = useMemo(() => {
    let a = 0;
    const inner = [], outer = [];
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

  const labels = useMemo(() => {
    const rad = (d) => ((d - 90) * Math.PI) / 180;
    const pt = (r, d) => [cx + r * Math.cos(rad(d)), cy + r * Math.sin(rad(d))];
    const all = rings.outer.map((s) => {
      const [ax, ay] = pt(R_OUT1 + 1, s.mid), [ex, ey] = pt(R_OUT1 + 14, s.mid);
      const right = Math.cos(rad(s.mid)) >= 0;
      return { ...s, ax, ay, ex, ey, right, y: ey, x: right ? cx + LABEL_X : cx - LABEL_X };
    });
    ["r", "l"].forEach((side) => {
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

  const halo = { stroke: C.ink, strokeWidth: 3.4, paintOrder: "stroke", strokeLinejoin: "round" };

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
                  <path d={arcPath(cx, cy, R_OUT1 - 4, R_OUT1, s.a0 + 0.6, s.a1 - 0.6)} fill={ALERT_COLOUR[lvl]} opacity={lvl === "breach" ? 0.95 : 0.8} />
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

          <text x={cx} y={cy - 6} textAnchor="middle" fill={C.ice} style={{ font: `500 25px ${F.mono}` }}>{money(plan.totalValue, meta.unitSuffix)}</text>
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
                {zoneW > 0 && (
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

function BandBar({ cur, target, band, max, watchFraction, level }) {
  const pc = (v) => `${(Math.max(0, Math.min(v, max)) / max) * 100}%`;
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
  const periods = performance.periods || [];
  const policy = allocation.alertPolicy;
  const wf = policy && isNum(policy.watchFraction) ? policy.watchFraction : null;
  const max = Math.max(...allocation.classes.map((c) => Math.max(c.currentPct || 0, c.targetPct + c.bandPct))) * 1.05;

  const th = { font: `10px ${F.body}`, letterSpacing: "0.1em", color: C.faint, textTransform: "uppercase", padding: "0 8px 7px", textAlign: "right", whiteSpace: "nowrap" };
  const td = { font: `13px ${F.mono}`, color: C.ice, padding: "5px 8px", textAlign: "right", whiteSpace: "nowrap" };
  const ret = (v) => ({ ...td, color: !isNum(v) ? C.faint : v < 0 ? C.warn : C.ice });

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
                      {periods.map((p, i) => <td key={p} style={ret(c.returns && c.returns[i])}>{sgn(c.returns && c.returns[i])}</td>)}
                    </tr>
                  );
                })}
              </Fragment>
            );
          })}

          <tr style={{ borderTop: `1px solid ${C.rule}` }}>
            <td style={{ ...td, textAlign: "left", paddingLeft: 0, font: `600 13px ${F.body}`, paddingTop: 10 }}>Total plan</td>
            <td /><td /><td style={{ ...td, paddingTop: 10 }}>100.0</td><td style={{ ...td, color: C.faint, paddingTop: 10 }}>100.0</td><td /><td />
            {periods.map((p, i) => <td key={p} style={{ ...ret(performance.total && performance.total[i]), paddingTop: 10, fontWeight: 600 }}>{sgn(performance.total && performance.total[i])}</td>)}
          </tr>
          {performance.benchmark && (
            <Fragment>
              <tr>
                <td style={{ ...td, textAlign: "left", paddingLeft: 0, font: `13px ${F.body}`, color: C.mist }}>{performance.benchmarkLabel || "Policy benchmark"}</td>
                <td /><td /><td /><td /><td /><td />
                {periods.map((p, i) => <td key={p} style={{ ...td, color: C.mist }}>{sgn(performance.benchmark[i])}</td>)}
              </tr>
              <tr>
                <td style={{ ...td, textAlign: "left", paddingLeft: 0, font: `13px ${F.body}`, color: C.faint }}>Excess</td>
                <td /><td /><td /><td /><td /><td />
                {periods.map((p, i) => {
                  const a = performance.total && performance.total[i], b = performance.benchmark[i];
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

function LiquidityTab() {
  const { liquidity, plan, meta } = useView();
  const u = meta.unitSuffix;
  const tiers = liquidity.tiers || [];
  const total = tiers.reduce((s, t) => s + t.value, 0) || 1;
  const f = liquidity.forecast12m || {};
  const flows = [
    { label: "Distributions", v: f.distributions },
    { label: "Investment income", v: f.income },
    { label: "Capital calls", v: isNum(f.calls) ? -f.calls : null },
    { label: liquidity.payoutLabel || "Benefit payments / spending", v: isNum(f.payout) ? -f.payout : null },
  ].filter((x) => isNum(x.v));
  const net = isNum(f.net) ? f.net : flows.reduce((s, x) => s + x.v, 0);
  const outflow = Math.abs(net) || 1;
  const maxF = Math.max(...flows.map((x) => Math.abs(x.v)), 1);
  const liquid = tiers.filter((t) => t.liquid !== false).reduce((s, t) => s + t.value, 0);
  const defensive = tiers.filter((t) => t.tier === 1 || t.tier === 2).reduce((s, t) => s + t.value, 0);
  const t1 = tiers.find((t) => t.tier === 1);

  return (
    <Fragment>
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <Tile label="Tier 1 · cash" value={money(t1 && t1.value, u)} sub={`${pct(((t1 ? t1.value : 0) / total) * 100)} of plan`}
          tone={t1 && t1.value / total < 0.02 ? C.warn : undefined} />
        <Tile label="Tiers 1–2 · defensive" value={money(defensive, u)} sub={pct((defensive / total) * 100) + " of plan"} />
        <Tile label="Liquid, tiers 1–3" value={money(liquid, u)} sub={pct((liquid / total) * 100) + " of plan"} />
        <Tile label="Net outflow, 12m" value={money(net, u)} sub={pct((outflow / plan.totalValue) * 100) + " of plan"} tone={C.warn} />
        <Tile label="Cover of 12m outflow" value={`${(liquid / outflow).toFixed(1)}×`} sub={`tiers 1–2 alone: ${(defensive / outflow).toFixed(1)}×`} tone={C.good} />
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
          <span style={{ width: 110, textAlign: "right" }}>COVER OF 12M OUTFLOW</span>
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
            <span style={{ width: 90, textAlign: "right", font: `14px ${F.mono}`, color: C.ice }}>{money(t.value, u)}</span>
            <span style={{ width: 60, textAlign: "right", font: `13px ${F.mono}`, color: C.faint }}>{pct((t.value / total) * 100)}</span>
            <span style={{ width: 110, textAlign: "right", font: `13px ${F.mono}`, color: C.mist }}>
              {t.liquid === false ? NA : `${(t.value / outflow).toFixed(1)}×`}
            </span>
          </div>
        ))}
        {liquidity.tierFootnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 10 }}>{liquidity.tierFootnote}</div>}
      </Panel>

      <Panel title="Anticipated cashflows" note={`next twelve months · ${meta.unitLabel}`} style={{ marginTop: 10 }}>
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
                  {x.v >= 0 ? "+" : ""}{money(x.v, u)}
                </span>
              </div>
            ))}
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderTop: `1px solid ${C.rule}` }}>
              <span style={{ font: `600 13px ${F.body}`, color: C.ice, width: 190 }}>Net</span>
              <span style={{ flex: 1 }} />
              <span style={{ font: `600 16px ${F.mono}`, color: net < 0 ? C.warn : C.good, width: 72, textAlign: "right" }}>{money(net, u)}</span>
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
                    <span style={{ marginLeft: "auto", font: `13px ${F.mono}`, color: s.value ? C.ice : C.faint }}>{money(s.value, u)}</span>
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
    </Fragment>
  );
}

/* ---------------------------------------------------------------- *
 *  PRIVATE CASHFLOWS TAB
 * ---------------------------------------------------------------- */

function CashflowBars({ rows, histCount }) {
  const W = 900, H = 250, L = 50, R = 20, T = 18, B = 30;
  const vals = rows.flatMap((r) => [r.distributions, -r.calls]);
  const hi = Math.max(...vals, 1) * 1.15, lo = Math.min(...vals, -1) * 1.15;
  const bw = (W - L - R) / rows.length;
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const zero = y(0), cut = L + bw * histCount;
  const step = Math.max(10, Math.round((hi - lo) / 5 / 10) * 10);
  const ticks = []; for (let v = Math.ceil(lo / step) * step; v < hi; v += step) ticks.push(v);

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

function RatioChart({ rows, histCount, series, domain, title, anchor }) {
  const W = 440, H = 180, L = 44, R = 14, T = 26, B = 26;
  const bw = (W - L - R) / rows.length;
  const y = (v) => T + (1 - (v - domain[0]) / (domain[1] - domain[0])) * (H - T - B);
  const cut = L + bw * histCount;
  const every = Math.ceil(rows.length / 5);
  return (
    <div style={{ flex: "1 1 340px", minWidth: 300 }}>
      <div style={{ font: `10px ${F.body}`, letterSpacing: "0.12em", color: C.faint, textTransform: "uppercase", marginBottom: 4 }}>{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
        {histCount < rows.length && <rect x={cut} y={T} width={W - R - cut} height={H - T - B} fill={C.ice} opacity={0.03} />}
        {[domain[0], (domain[0] + domain[1]) / 2, domain[1]].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={C.ruleSoft} />
            <text x={L - 7} y={y(v) + 3.5} textAnchor="end" fill={C.faint} style={{ font: `10px ${F.mono}` }}>{v.toFixed(2)}</text>
          </g>
        ))}
        {series.map((s) => (
          <g key={s.label}>
            <path d={rows.map((r, i) => `${i ? "L" : "M"}${(L + bw * (i + 0.5)).toFixed(1)},${y(s.get(r)).toFixed(1)}`).join(" ")} fill="none" stroke={s.c} strokeWidth={1.9} />
            <circle cx={L + bw * (histCount - 0.5)} cy={y(s.get(rows[histCount - 1]))} r={2.6} fill={s.c} />
          </g>
        ))}
        {isNum(anchor) && anchor > domain[0] && anchor < domain[1] && (
          <g>
            <line x1={L} x2={W - R} y1={y(anchor)} y2={y(anchor)} stroke={C.warn} strokeDasharray="4 3" opacity={0.6} />
            <text x={W - R} y={y(anchor) - 5} textAnchor="end" fill={C.warn} style={{ font: `10px ${F.body}` }}>{num(anchor)} anchor</text>
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

function PrivateTab() {
  const { privateCashflows: pcf, plan, liquidity, meta } = useView();
  const [sel, setSel] = useState("aggregate");
  const u = meta.unitSuffix;
  if (!pcf || !pcf.series) return <Empty what="private cashflow series" />;

  const options = [{ id: "aggregate", label: pcf.aggregateLabel || "Aggregate" }].concat(pcf.classes);
  const rows = pcf.series[sel] || pcf.series.aggregate;
  const H = pcf.histCount;
  const sum = (a, k) => a.reduce((s, r) => s + (r[k] || 0), 0);
  const ltm = rows.slice(Math.max(0, H - 4), H);
  const fwd = rows.slice(H, H + 4);
  const cur = rows[H - 1];
  const anchor = liquidity && liquidity.coverageAnchor;
  const danger = liquidity && liquidity.coverageDanger;

  const covVals = rows.map((r) => r.coverage).filter(isNum);
  const covDom = [Math.max(0, Math.min(...covVals) - 0.1), Math.max(...covVals) + 0.1];
  const rateVals = rows.flatMap((r) => [r.callRateUnfunded, r.callRateNav]).filter(isNum);
  const rateDom = [0, Math.max(...rateVals) * 1.25];

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
        <Tile label="NAV" value={money(cur.navClose, u)} sub={`${pct((cur.navClose / plan.totalValue) * 100)} of plan`} />
        <Tile label="Unfunded" value={money(cur.unfundedClose, u)} />
        <Tile label="Unfunded ÷ NAV" value={num(cur.coverage)} sub={isNum(anchor) ? `${num(anchor)} anchor` : undefined}
          tone={isNum(danger) && cur.coverage > danger ? C.warn : undefined} />
        <Tile label="Calls ÷ unfunded" value={pct(cur.callRateUnfunded * 100)} sub="quarterly call rate" />
        <Tile label="Calls ÷ NAV" value={pct(cur.callRateNav * 100)} sub="quarterly" />
        <Tile label="Net cashflow, LTM" value={money(sum(ltm, "net"), u)} tone={sum(ltm, "net") < 0 ? C.warn : C.good}
          sub={fwd.length ? `next 4q: ${money(sum(fwd, "net"), u)}` : undefined} />
      </div>

      <Panel title="Capital calls, distributions and net"
        note={`${meta.unitLabel} per quarter · ${H} realised, ${rows.length - H} forecast`}
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
                {["Asset class", "NAV", "Unfunded", "Unf ÷ NAV", "Calls LTM", "Dists LTM", "Net LTM", "Call rate", "Net next 4q"].map((h, i) => (
                  <th key={h} style={{ font: `10px ${F.body}`, letterSpacing: "0.1em", color: C.faint, textTransform: "uppercase", padding: "0 8px 7px", textAlign: i ? "right" : "left" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pcf.classes.concat([{ id: "aggregate", label: pcf.aggregateLabel || "Aggregate" }]).map((cl) => {
                const rs = pcf.series[cl.id]; if (!rs) return null;
                const h = rs.slice(Math.max(0, H - 4), H), fw = rs.slice(H, H + 4), c = rs[H - 1];
                const s = (a, k) => a.reduce((x, r) => x + (r[k] || 0), 0);
                const agg = cl.id === "aggregate";
                const td = { font: `13px ${F.mono}`, color: C.ice, padding: "6px 8px", textAlign: "right" };
                return (
                  <tr key={cl.id} onClick={() => setSel(cl.id)} style={{ borderTop: `1px solid ${agg ? C.rule : C.ruleSoft}`, cursor: "pointer" }}>
                    <td style={{ ...td, textAlign: "left", font: `${agg ? 600 : 400} 13px ${F.body}`, color: sel === cl.id ? C.amber : C.mist }}>{cl.label}</td>
                    <td style={td}>{money(c.navClose, u)}</td>
                    <td style={td}>{money(c.unfundedClose, u)}</td>
                    <td style={{ ...td, color: isNum(danger) && c.coverage > danger ? C.warn : C.ice }}>{num(c.coverage)}</td>
                    <td style={td}>{money(s(h, "calls"), u)}</td>
                    <td style={td}>{money(s(h, "distributions"), u)}</td>
                    <td style={{ ...td, color: s(h, "net") < 0 ? C.warn : C.good }}>{money(s(h, "net"), u)}</td>
                    <td style={{ ...td, color: C.mist }}>{pct(c.callRateUnfunded * 100)}</td>
                    <td style={{ ...td, color: s(fw, "net") < 0 ? C.warn : C.good }}>{fw.length ? money(s(fw, "net"), u) : NA}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {pcf.footnote && <div style={{ font: `11px ${F.body}`, color: C.faint, marginTop: 8 }}>{pcf.footnote}</div>}
      </Panel>
    </Fragment>
  );
}

/* ---------------------------------------------------------------- *
 *  MARKETS TAB
 * ---------------------------------------------------------------- */

function SeriesChart({ s, indexed, height }) {
  const W = 420, H = height, T = 12, B = 24, L = 40, R = 40;
  const N = s.path.length - 1;
  const lo = Math.min(...s.path) * (indexed ? 0.97 : 0.9), hi = Math.max(...s.path) * (indexed ? 1.03 : 1.08);
  const x = (m) => L + (m / N) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const d = s.path.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = s.path[N], dp = s.dp == null ? 0 : s.dp;
  const gid = `g-${s.id}`;
  const xTicks = []; for (let m = N; m >= 0; m -= 12) xTicks.unshift(m);

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

function MarketCard({ s, periods, indexed = true, height = 150 }) {
  const N = s.path.length - 1;
  const last = s.path[N];
  const chg = indexed ? (last / s.path[0] - 1) * 100 : last - s.path[0];
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
      {s.returns && periods && (
        <div style={{ display: "flex", borderTop: `1px solid ${C.ruleSoft}`, marginTop: 6, paddingTop: 6 }}>
          {periods.map((p, i) => (
            <div key={p} style={{ flex: 1, textAlign: "center" }}>
              <div style={{ font: `9px ${F.body}`, color: C.faint, letterSpacing: "0.08em" }}>{p}</div>
              <div style={{ font: `12px ${F.mono}`, color: !isNum(s.returns[i]) ? C.faint : s.returns[i] < 0 ? C.warn : C.ice }}>{sgn(s.returns[i])}</div>
            </div>
          ))}
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

const TABS = [["plan", "Plan"], ["liquidity", "Liquidity"], ["private", "Private cashflows"], ["markets", "Markets"]];

export default function CIODashboard({ view: viewProp, onPlaneChange, initialTab = "plan" }) {
  const [tab, setTab] = useState(initialTab);
  const [localPlane, setLocalPlane] = useState("reported");
  const mock = useMemo(() => makeSampleView(localPlane), [localPlane]);
  const view = viewProp || mock;
  const { meta, plan } = view;
  const setPlane = (p) => (onPlaneChange ? onPlaneChange(p) : setLocalPlane(p));
  const planes = meta.planesAvailable || ["reported"];

  return (
    <ViewCtx.Provider value={view}>
      <div style={{ background: C.ink, minHeight: "100vh", padding: "18px 20px 40px", color: C.ice, font: `14px ${F.body}` }}>
        <div style={{ maxWidth: 1220, margin: "0 auto" }}>
          <header style={{ display: "flex", alignItems: "flex-end", gap: 20, flexWrap: "wrap", paddingBottom: 12 }}>
            <div>
              <div style={{ font: `10px ${F.body}`, letterSpacing: "0.22em", color: C.faint }}>TERRARIUM · CIO DASHBOARD</div>
              <h1 style={{ font: `400 29px ${F.display}`, margin: "4px 0 0" }}>{meta.worldTitle}</h1>
            </div>
            <div style={{ font: `12px ${F.mono}`, color: C.faint, paddingBottom: 4 }}>
              seed {meta.seed} · {meta.asOfLabel} · linkage {meta.linkageVersion}
            </div>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14, paddingBottom: 2 }}>
              {meta.regime && <span style={{ font: `12px ${F.body}`, color: C.warn, letterSpacing: "0.1em" }}>REGIME · {meta.regime.toUpperCase()}</span>}
              {planes.length > 1 && (
                <div style={{ display: "flex", border: `1px solid ${C.rule}`, borderRadius: 2, overflow: "hidden" }}>
                  {planes.map((k) => (
                    <button key={k} onClick={() => setPlane(k)} style={{
                      padding: "6px 14px", cursor: "pointer", border: "none", font: `13px ${F.body}`,
                      background: meta.plane === k ? C.ice : "transparent", color: meta.plane === k ? C.ink : C.mist,
                    }}>{k === "true" ? "True" : "Reported"}</button>
                  ))}
                </div>
              )}
            </div>
          </header>

          <nav style={{ display: "flex", gap: 26, borderBottom: `1px solid ${C.rule}`, marginBottom: 12 }}>
            {TABS.map(([k, l]) => (
              <button key={k} onClick={() => setTab(k)} style={{
                background: "none", border: "none", cursor: "pointer", padding: "0 0 9px",
                font: `${tab === k ? 600 : 400} 15px ${F.body}`, color: tab === k ? C.ice : C.faint,
                borderBottom: `2px solid ${tab === k ? C.amber : "transparent"}`, marginBottom: -1,
              }}>{l}</button>
            ))}
          </nav>

          {tab === "plan" && (
            <Fragment>
              <Panel title="Plan growth" note={`${plan.windowLabel || "five years"} · ${meta.unitLabel}`}
                right={
                  <div style={{ display: "flex", gap: 16, font: `12px ${F.body}`, color: C.faint }}>
                    <span>Now <b style={{ color: C.ice, font: `13px ${F.mono}` }}>{money(plan.totalValue, meta.unitSuffix)}</b></span>
                    {isNum(plan.growthPct) && <span>Growth <b style={{ color: plan.growthPct >= 0 ? C.good : C.warn, font: `13px ${F.mono}` }}>{sgn(plan.growthPct)}%</b></span>}
                    {isNum(plan.netOfFlows) && <span>Net of flows <b style={{ color: C.ice, font: `13px ${F.mono}` }}>{money(plan.netOfFlows, meta.unitSuffix)}</b></span>}
                  </div>
                }>
                <PlanGrowth />
              </Panel>

              <Panel title="Asset allocation" note="by goal · current weights" style={{ marginTop: 10 }}
                right={<AlertSummary counts={allocationAlerts(view.allocation)} />}>
                <AllocationDonut />
              </Panel>

              <Panel title="Performance and allocation" note={meta.plane === "true" ? "true plane" : "reported plane"} style={{ marginTop: 10 }}
                right={<AlertSummary counts={allocationAlerts(view.allocation)} />}>
                <PerfTable />
              </Panel>
            </Fragment>
          )}

          {tab === "liquidity" && <LiquidityTab />}
          {tab === "private" && <PrivateTab />}
          {tab === "markets" && <MarketsTab />}

          <footer style={{ marginTop: 18, paddingTop: 12, borderTop: `1px solid ${C.ruleSoft}`, font: `11px ${F.body}`, color: C.faint, display: "flex", gap: 18, flexWrap: "wrap" }}>
            <span style={{ letterSpacing: "0.14em" }}>{meta.watermark || "SIMULATED WORLD — NOT A FORECAST"}</span>
            <span>{meta.disclaimer}</span>
            <span style={{ marginLeft: "auto", font: `11px ${F.mono}` }}>run {meta.runId} · replayable from RunRecord</span>
          </footer>
        </div>
      </div>
    </ViewCtx.Provider>
  );
}

/* ==================================================================
 *  MOCK DATA — DELETE THIS ENTIRE BLOCK ON WIRE-UP
 *  Exists only to give the renderer a payload of the right shape.
 *  It is not a model and must not be reused as one.
 * ================================================================== */

function lerpPath(points, n) {
  const out = [];
  for (let m = 0; m <= n; m++) {
    let i = 0;
    while (i < points.length - 2 && points[i + 1][0] < m) i++;
    const [x0, y0] = points[i], [x1, y1] = points[i + 1];
    out.push(y0 + (y1 - y0) * (x1 === x0 ? 0 : (m - x0) / (x1 - x0)));
  }
  return out;
}
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function noisy(arr, seed, amp) {
  const rnd = mulberry32(seed);
  return arr.map((v, i) => (i === 0 ? v : v * (1 + (rnd() - 0.5) * amp)));
}

const MOCK_CLASSES = [
  ["equity", "Global equity", "growth", 28, 3.0, 24.0, [2.8, 6.4, 11.2, 7.9, 11.4, 9.6], false],
  ["buyout", "Buyout", "growth", 14, 3.0, 17.4, [1.1, 2.4, 4.8, 6.2, 13.1, 12.4], true],
  ["venture", "Venture & growth", "growth", 6, 2.0, 8.1, [-0.6, -1.4, -3.2, -4.8, 9.7, 11.8], true],
  ["re", "Real estate", "real", 8, 2.0, 9.6, [-1.2, -2.9, -6.4, -1.1, 3.8, 6.2], true],
  ["infra", "Infrastructure", "real", 6, 2.0, 6.6, [1.9, 4.1, 8.2, 9.4, 8.1, 8.8], true],
  ["natres", "Natural resources", "real", 3, 1.5, 2.4, [3.4, 5.2, 6.1, 4.2, 6.9, 3.1], true],
  ["corefi", "Core fixed income", "income", 12, 2.0, 10.2, [1.4, 3.1, 5.4, 1.2, 0.4, 1.9], false],
  ["pcredit", "Private credit", "income", 8, 2.0, 9.1, [2.2, 4.6, 9.1, 9.8, 8.4, 7.6], true],
  ["hy", "High yield & EMD", "income", 4, 1.5, 3.5, [1.8, 4.2, 8.4, 5.1, 4.2, 4.7], false],
  ["absret", "Absolute return", "diversifier", 7, 2.0, 6.2, [1.2, 2.8, 6.2, 5.4, 5.1, 4.2], false],
  ["trend", "Trend / macro", "diversifier", 2, 1.0, 1.5, [-2.1, -3.4, -1.8, 2.2, 4.6, 3.4], false],
  ["cash", "Cash", "diversifier", 2, 2.0, 1.4, [1.1, 2.2, 4.6, 3.8, 2.3, 1.6], false],
];

const MOCK_PM = [
  { id: "buyout", nav0: 379, unf0: 212, rc: 0.070, dr: 0.055, ret: 0.022, commit: 26 },
  { id: "venture", nav0: 178, unf0: 96, rc: 0.055, dr: 0.026, ret: 0.004, commit: 10 },
  { id: "pcredit", nav0: 206, unf0: 118, rc: 0.095, dr: 0.078, ret: 0.024, commit: 18 },
  { id: "re", nav0: 214, unf0: 74, rc: 0.060, dr: 0.040, ret: -0.006, commit: 9 },
  { id: "infra", nav0: 156, unf0: 82, rc: 0.055, dr: 0.034, ret: 0.020, commit: 9 },
  { id: "natres", nav0: 67, unf0: 31, rc: 0.058, dr: 0.046, ret: 0.014, commit: 4 },
];

function makeSampleView(plane) {
  const PLAN_V = 2400, M = 60, NH = 12, NF = 6;
  const trueF = plane === "true" ? 1.068 : 1;

  const raw = MOCK_CLASSES.map(([id, label, goalId, targetPct, bandPct, cur, returns, priv]) => ({
    id, label, goalId, targetPct, bandPct, returns, priv, currentPct: priv ? cur * trueF : cur,
  }));
  const privSum = raw.filter((c) => c.priv).reduce((s, c) => s + c.currentPct, 0);
  const cashPct = raw.find((c) => c.id === "cash").currentPct;
  const pubTarget = 100 - privSum - cashPct;
  const pubSum = raw.filter((c) => !c.priv && c.id !== "cash").reduce((s, c) => s + c.currentPct, 0);
  const classes = raw
    .map((c) => ({ ...c, currentPct: c.priv || c.id === "cash" ? c.currentPct : (c.currentPct / pubSum) * pubTarget }))
    .map((c) => ({ ...c, value: (c.currentPct / 100) * PLAN_V }));

  const callM = [1, 1.05, 1.1, 1, 0.95, 0.9, 0.85, 0.8, 0.75, 0.72, 0.7, 0.72, 0.75, 0.8, 0.85, 0.85, 0.9, 0.9];
  const distM = [1, 1.05, 0.95, 1, 0.9, 0.75, 0.55, 0.42, 0.35, 0.3, 0.32, 0.38, 0.46, 0.56, 0.66, 0.76, 0.84, 0.9];
  const retM = [1.1, 1, 0.9, 0.6, 0.1, -0.8, -1.4, -0.9, -0.2, 0.4, 0.8, 1, 1, 1, 1.05, 1.05, 1, 1];
  const qlab = []; { let y = 1, q = 4; for (let i = 0; i < NH + NF; i++) { qlab.push(`Y${y}Q${q}`); if (++q > 4) { q = 1; y++; } } }

  const series = {};
  MOCK_PM.forEach((p) => {
    let nav = p.nav0 * trueF, unf = p.unf0;
    series[p.id] = qlab.map((label, i) => {
      const calls = p.rc * callM[i] * unf, dists = p.dr * distM[i] * nav;
      const navOpen = nav, unfOpen = unf;
      nav = nav * (1 + p.ret * retM[i]) + calls - dists;
      unf = unf - calls + p.commit * (i >= NH ? 0.85 : 1);
      return {
        label, forecast: i >= NH, calls, distributions: dists, net: dists - calls,
        navOpen, navClose: nav, unfundedOpen: unfOpen, unfundedClose: unf,
        callRateUnfunded: calls / unfOpen, callRateNav: calls / navOpen, coverage: unf / nav,
      };
    });
  });
  series.aggregate = qlab.map((label, i) => {
    const s = MOCK_PM.reduce((a, p) => {
      const r = series[p.id][i];
      ["calls", "distributions", "navOpen", "navClose", "unfundedOpen", "unfundedClose"].forEach((k) => { a[k] += r[k]; });
      return a;
    }, { calls: 0, distributions: 0, navOpen: 0, navClose: 0, unfundedOpen: 0, unfundedClose: 0 });
    return {
      label, forecast: i >= NH, ...s, net: s.distributions - s.calls,
      callRateUnfunded: s.calls / s.unfundedOpen, callRateNav: s.calls / s.navOpen, coverage: s.unfundedClose / s.navClose,
    };
  });

  const cur = series.aggregate[NH - 1];
  const tierValue = (ids) => classes.filter((c) => ids.indexOf(c.id) >= 0).reduce((s, c) => s + c.value, 0);

  return {
    meta: {
      runId: "4471-B", seed: "4471-B", worldTitle: "The Long Drought", worldVersion: "1.2",
      linkageVersion: "public-0.1", decisionAlphaVersion: "1.0",
      asOfLabel: "Y4 Q3", regime: "Drought",
      plane, planesAvailable: ["reported", "true"],
      unitLabel: "$m", unitSuffix: "m", currency: "USD",
      watermark: "SIMULATED WORLD — NOT A FORECAST",
      disclaimer: "Not investment advice. Generic parameters; not representative of any institution's policy portfolio.",
    },
    plan: {
      totalValue: PLAN_V, growthPct: 34.8, netOfFlows: 620, windowLabel: "five years",
      preRunLabel: "Before the world", worldStartLabel: "World begins · Y1 Q1",
      history: {
        worldStartIndex: 15,
        values: noisy(lerpPath([[0, 1780], [14, 1990], [26, 2210], [34, 2380], [42, 2120], [50, 2255], [60, PLAN_V]], M), 991, 0.012),
      },
    },
    allocation: {
      goals: [
        { id: "growth", label: "Growth", tolerancePct: 1.5 },
        { id: "real", label: "Real return", tolerancePct: 1.5 },
        { id: "income", label: "Income", tolerancePct: 1.5 },
        { id: "diversifier", label: "Diversifiers", tolerancePct: 1.5 },
      ],
      classes,
      alertPolicy: { watchFraction: 0.75, label: "Amber inside the last quarter of the band" },
    },
    performance: {
      periods: ["1Q", "YTD", "1Y", "3Y", "5Y", "10Y"],
      annualisedFromIndex: 3,
      total: [1.6, 3.6, 6.8, 5.4, 8.2, 7.4],
      benchmark: [1.8, 3.9, 7.2, 5.1, 7.9, 7.2],
      benchmarkLabel: "Policy benchmark",
      footnote: "1Q and YTD are period returns; 3Y, 5Y and 10Y are annualised. Private classes are reported on the appraised basis with a one-quarter lag.",
    },
    liquidity: {
      tiers: [
        { id: "t1", tier: 1, label: "Cash", note: "Operating cash and T-bills", value: tierValue(["cash"]), colour: C.good },
        { id: "t2", tier: 2, label: "Liquid / uncorrelated", note: "Core fixed income, absolute return, trend", value: tierValue(["corefi", "absret", "trend"]), colour: C.blue },
        { id: "t3", tier: 3, label: "Liquid / correlated", note: "Global equity, high yield & EMD", value: tierValue(["equity", "hy"]), colour: C.amber },
        { id: "il", label: "Illiquid", note: "Private markets NAV", value: tierValue(["buyout", "venture", "pcredit", "re", "infra", "natres"]), colour: C.faint, liquid: false },
      ],
      forecast12m: { distributions: 94, income: 42, calls: 186, payout: 112, net: -162 },
      payoutLabel: "Benefit payments / spending",
      unfundedToNav: cur.coverage, coverageAnchor: 0.5, coverageDanger: 0.65,
      sourcing: [
        { label: "Distributions and income", value: 136, colour: C.good },
        { label: "Tier 1 cash drawn", value: 34, colour: C.blue },
        { label: "Tier 2 sales", value: 128, colour: C.amber },
        { label: "Tier 3 sales", value: 0, colour: C.warn },
      ],
      tierFootnote: "Tier 3 is liquid but sells at the wrong moment: it falls with the drawdown that creates the need for it. Tier 2 is the only sleeve that is both saleable and uncorrelated.",
      flowFootnote: "Spending is set off a trailing average of reported values, so the payout holds up while true value falls. Calls arrive on the funds' schedule and are the only line here the plan cannot decline.",
      sourcingFootnote: "The waterfall meets the year without touching tier 3, by spending cash down to a level that leaves nothing for a second bad year.",
    },
    privateCashflows: {
      histCount: NH,
      classes: MOCK_PM.map((p) => ({ id: p.id, label: classes.find((c) => c.id === p.id).label })),
      series,
      footnote: "Call rate is calls over opening unfunded for the quarter. Forecast holds the pacing schedule fixed and applies the current linkage calibration; it is not a commitment.",
    },
    markets: {
      tiles: [
        { label: "Regime", value: "Drought", sub: "quarter 5 · previous: stress", tone: "warn" },
        { label: "Policy rate", value: "3.75%", sub: "−150bp from peak" },
        { label: "CPI, y/y", value: "3.2%", sub: "peak 8.4% at −34m" },
        { label: "IG spread", value: "138bp", sub: "widest 240bp at −20m" },
        { label: "Equity drawdown", value: "−21.4%", sub: "trough at −17m · recovered 78%", tone: "warn" },
      ],
      returns: [
        { id: "equity", label: "Equities", colour: C.amber, dp: 0, returns: [2.8, 6.4, 11.2, 7.9, 11.4, 9.6], path: noisy(lerpPath([[0, 100], [16, 124], [30, 148], [38, 168], [43, 132], [50, 152], [60, 168]], M), 12, 0.026) },
        { id: "bonds", label: "Bonds", colour: C.blue, dp: 0, returns: [1.4, 3.1, 5.4, 1.2, 0.4, 1.9], path: noisy(lerpPath([[0, 100], [14, 104], [26, 101], [36, 90], [44, 88], [52, 98], [60, 104]], M), 77, 0.012) },
        { id: "credit", label: "Credit", colour: C.good, dp: 0, returns: [1.8, 4.2, 8.4, 5.1, 4.2, 4.7], path: noisy(lerpPath([[0, 100], [16, 110], [30, 120], [40, 112], [46, 116], [60, 128]], M), 45, 0.016) },
      ],
      conditions: [
        { id: "policy", label: "Policy rate", unit: "%", dp: 2, colour: C.amber, path: noisy(lerpPath([[0, 0.5], [12, 0.5], [24, 2.8], [33, 5.25], [44, 5.25], [52, 4.25], [60, 3.75]], M), 301, 0.02) },
        { id: "cpi", label: "CPI, year on year", unit: "%", dp: 1, colour: C.warn, path: noisy(lerpPath([[0, 2.1], [14, 4.6], [26, 8.4], [36, 5.2], [46, 3.6], [60, 3.2]], M), 302, 0.045) },
        { id: "spread", label: "IG credit spread", unit: "bps", dp: 0, colour: C.blue, path: noisy(lerpPath([[0, 105], [16, 132], [30, 186], [40, 240], [48, 164], [60, 138]], M), 303, 0.055) },
      ],
      correlations: [
        { id: "bonds", label: "Bonds", current: 0.31, baseline: -0.12 },
        { id: "credit", label: "Credit", current: 0.79, baseline: 0.64 },
        { id: "re", label: "Real estate", current: 0.52, baseline: 0.38 },
        { id: "absret", label: "Absolute return", current: 0.58, baseline: 0.41 },
        { id: "trend", label: "Trend / macro", current: -0.34, baseline: -0.22 },
        { id: "infra", label: "Infrastructure", current: 0.44, baseline: 0.29 },
      ],
      correlationNote: "rolling 36-month, against global equity",
      returnsFootnote: "1Q and YTD are period returns; 3Y, 5Y and 10Y are annualised.",
      conditionsFootnote: "These are the slow states the generator specifies directly. Month-level market paths are drawn conditional on them, not the other way round.",
      correlationFootnote: "Diversifiers have converged toward equity over the drawdown — the pattern the goal-based allocation is meant to survive, shown here rather than asserted.",
    },
  };
}
