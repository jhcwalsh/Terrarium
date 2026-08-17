/**
 * VintageChart.tsx — per-vintage paid-in/unfunded stacked bars with a NAV
 * line across vintages (app-open-02 task 10, owner-dictated 2026-08-16):
 * "Each historical commitment table should have a chart with a bar per
 * vintage with paid in and unfunded as stacked bars per vintage, and a line
 * that [runs] with the NAV for each vintage."
 *
 * Pure SVG, no chart library — the app's existing idiom (FanChart.tsx;
 * CashflowBars/RatioChart in components/CioDashboard.tsx): hand-rolled
 * markup, a className per element with the colours living in styles.css.
 *
 * Input is exactly the document shape BookEntry's own ladder table already
 * reads — a `Rung[]`, the same array `book.private[sleeve]` holds
 * (`rungField`'s own field names: `commitment.paid_in`/`.unfunded`,
 * `value.nav_true` — see BookEntry.tsx), never a reshaped copy. BookEntry
 * passes its LIVE typed state straight through, so editing a rung input
 * moves this chart on the very next render: there is no local snapshot here
 * and nothing memoizes the prop away.
 *
 * ONE y axis (house dataviz rule — no dual axes): paid-in, unfunded and NAV
 * are all "allocation points", the same unit the rest of the book-entry
 * screen totals to 100 in, so all three legitimately share one scale. The
 * domain is `max(paid_in + unfunded, nav_true)` across every rung, padded
 * 5% — and never zero, so an all-zero ladder still gets a domain to draw an
 * honest flat zero against rather than dividing by it.
 *
 * A dollar figure rides alongside the points figure via `usd()`, same
 * treatment as the rest of the screen, but only where a SPECIFIC value is
 * shown: a native SVG `<title>` per bar segment and NAV marker is enough —
 * no second axis, no JS hover machinery.
 */

import type { Rung } from "../lib/session";
import { usd } from "../lib/money";

/** Gap, in SVG user units, between the paid-in and unfunded segments of one
 * bar — keeps the two segments visibly distinct even when one is small. */
const SEGMENT_GAP = 2;

interface VintagePoint {
  index: number;
  vintageYear: number;
  paidIn: number;
  unfunded: number;
  navTrue: number;
}

function toPoints(rungs: Rung[]): VintagePoint[] {
  return rungs.map((r, index) => ({
    index,
    vintageYear: r.identity.vintage_year,
    paidIn: r.commitment.paid_in,
    unfunded: r.commitment.unfunded,
    navTrue: r.value.nav_true,
  }));
}

export function VintageChart({ rungs }: { rungs: Rung[] }) {
  // an empty ladder renders nothing at all — there is no vintage to plot,
  // and an empty chart frame would just be a lie about there being data.
  if (!rungs || rungs.length === 0) return null;

  const data = toPoints(rungs);

  const W = 900;
  const H = 190;
  const L = 40;
  const R = 14;
  const T = 14;
  const B = 26;
  const plotH = H - T - B;
  const n = data.length;
  const bw = (W - L - R) / n;
  const barW = Math.max(4, bw * 0.5);

  // the shared scale: the larger of a rung's own committed stack
  // (paid_in + unfunded) and its NAV, maxed across every rung, padded 5%.
  // Guarded at a floor of 1 so an all-zero ladder still gets a real domain
  // instead of a 0/0 division.
  const rawMax = Math.max(0, ...data.map((d) => Math.max(d.paidIn + d.unfunded, d.navTrue)));
  const maxVal = rawMax > 0 ? rawMax * 1.05 : 1;

  const y = (v: number) => T + (1 - Math.max(0, v) / maxVal) * plotH;
  const baseline = y(0);
  const cx = (i: number) => L + bw * (i + 0.5);

  const navPath = data
    .map((d, i) => `${i ? "L" : "M"}${cx(d.index).toFixed(1)},${y(d.navTrue).toFixed(1)}`)
    .join(" ");

  return (
    <div className="vintage-chart" data-testid="vintage-chart">
      <svg
        className="vintage-chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Paid-in and unfunded by vintage, with NAV"
      >
        <line className="vintage-baseline" x1={L} x2={W - R} y1={baseline} y2={baseline} />

        {/* axis end labels only — 0 and the scale's own max, one decimal */}
        <text className="vintage-axis-label" x={L - 5} y={baseline - 2} textAnchor="end">
          0.0
          <title>{usd(0)}</title>
        </text>
        <text className="vintage-axis-label" x={L - 5} y={y(maxVal) + 8} textAnchor="end">
          {maxVal.toFixed(1)}
          <title>{usd(maxVal)}</title>
        </text>

        {data.map((d) => {
          const x0 = L + bw * d.index + (bw - barW) / 2;
          // paid-in sits on the baseline; unfunded stacks above it with a
          // fixed pixel gap, so the two segments read as distinct even when
          // one of them is zero height.
          const paidTop = y(d.paidIn);
          const paidHeight = Math.max(0, baseline - paidTop);
          const unfundedBottom = paidTop - SEGMENT_GAP;
          const unfundedTop = y(d.paidIn + d.unfunded);
          const unfundedHeight = Math.max(0, unfundedBottom - unfundedTop);
          return (
            <g key={d.index}>
              <rect
                className="vintage-bar-paid"
                data-testid={`vintage-bar-paid-${d.index}`}
                x={x0}
                y={paidTop}
                width={barW}
                height={paidHeight}
              >
                <title>{`vintage ${d.index}: paid in ${d.paidIn.toFixed(1)} (${usd(d.paidIn)})`}</title>
              </rect>
              <rect
                className="vintage-bar-unfunded"
                data-testid={`vintage-bar-unfunded-${d.index}`}
                x={x0}
                y={unfundedTop}
                width={barW}
                height={unfundedHeight}
              >
                <title>{`vintage ${d.index}: unfunded ${d.unfunded.toFixed(1)} (${usd(d.unfunded)})`}</title>
              </rect>
              <text className="vintage-tick-label" x={cx(d.index)} y={H - 8} textAnchor="middle">
                {Number.isFinite(d.vintageYear) ? d.vintageYear : `#${d.index}`}
              </text>
            </g>
          );
        })}

        <path className="vintage-nav-line" d={navPath} />

        {data.map((d) => (
          <circle
            key={d.index}
            className="vintage-nav-marker"
            data-testid={`vintage-nav-${d.index}`}
            cx={cx(d.index)}
            cy={y(d.navTrue)}
            r={3}
          >
            <title>{`vintage ${d.index}: NAV ${d.navTrue.toFixed(1)} (${usd(d.navTrue)})`}</title>
          </circle>
        ))}
      </svg>
      <div className="vintage-chart-legend">
        <span className="vintage-chart-legend-item">
          <span className="vintage-chart-swatch vintage-chart-swatch-paid" /> Paid in
        </span>
        <span className="vintage-chart-legend-item">
          <span className="vintage-chart-swatch vintage-chart-swatch-unfunded" /> Unfunded
        </span>
        <span className="vintage-chart-legend-item">
          <span className="vintage-chart-swatch vintage-chart-swatch-nav" /> NAV
        </span>
      </div>
    </div>
  );
}
