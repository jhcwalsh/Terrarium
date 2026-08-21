/**
 * ProjectionChart.tsx — one private class's commitment plan and projected
 * NAV over the next ten years (app-open-04 Item H, owner drive item 6:
 * "one panel per asset class, like the historical vintages, showing the
 * commitment, projected NAVs for the next 10 years").
 *
 * The visual pattern is VintageChart's, deliberately: one bar per YEAR
 * (the year's planned commitment) with a NAV line across the years — the
 * same classes, so styles.css's vintage-chart rules paint both and the two
 * tabs read as one system. Where VintageChart's x-axis is vintages of the
 * PAST, this one's is years of the plan AHEAD.
 *
 * Every number is SERVED: commitments are the plan grid's own values
 * (`plan.points[sleeve]`, the served/derived document) and the NAV path is
 * `projection[sleeve].nav_years` from the server's `plan_projection` — the
 * pacing model's own cohort recursion at tier-0's frozen constant G. This
 * component computes nothing but pixel positions (DN-3 W5).
 */

import { usd } from "../lib/money";

/** Gap between segments, kept for visual parity with VintageChart. */
const W = 900;
const H = 190;
const L = 40;
const R = 14;
const T = 14;
const B = 26;

export function ProjectionChart({
  sleeve,
  commitments,
  navYears,
}: {
  sleeve: string;
  /** the plan's committed points per year, in window order (year k+1). */
  commitments: number[];
  /** the server-projected year-end NAV per year. */
  navYears: number[];
}) {
  // no projection served (older server, test fixtures) — render nothing
  // rather than an empty frame lying about there being data.
  if (!navYears || navYears.length === 0) return null;

  const n = navYears.length;
  const plotH = H - T - B;
  const bw = (W - L - R) / n;
  const barW = Math.max(4, bw * 0.5);

  const rawMax = Math.max(
    0,
    ...navYears,
    ...commitments.filter((c) => Number.isFinite(c)),
  );
  const maxVal = rawMax > 0 ? rawMax * 1.05 : 1;
  const y = (v: number) => T + (1 - Math.max(0, v) / maxVal) * plotH;
  const baseline = y(0);
  const cx = (i: number) => L + bw * (i + 0.5);

  const navPath = navYears
    .map((v, i) => `${i ? "L" : "M"}${cx(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join(" ");

  return (
    <div className="vintage-chart" data-testid={`projection-chart-${sleeve}`}>
      <svg
        className="vintage-chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Planned commitments and projected NAV by year for ${sleeve}`}
      >
        <line className="vintage-baseline" x1={L} x2={W - R} y1={baseline} y2={baseline} />
        <text className="vintage-axis-label" x={L - 5} y={baseline - 2} textAnchor="end">
          0.0
          <title>{usd(0)}</title>
        </text>
        <text className="vintage-axis-label" x={L - 5} y={y(maxVal) + 8} textAnchor="end">
          {maxVal.toFixed(1)}
          <title>{usd(maxVal)}</title>
        </text>

        {navYears.map((_, i) => {
          const committed = commitments[i] ?? 0;
          const x0 = L + bw * i + (bw - barW) / 2;
          const top = y(committed);
          return (
            <g key={i}>
              {committed > 0 && (
                <rect
                  className="vintage-bar-paid"
                  data-testid={`projection-bar-${sleeve}-${i}`}
                  x={x0}
                  y={top}
                  width={barW}
                  height={Math.max(0, baseline - top)}
                >
                  <title>{`year ${i + 1}: committed ${committed.toFixed(1)} (${usd(committed)})`}</title>
                </rect>
              )}
              <text className="vintage-tick-label" x={cx(i)} y={H - 8} textAnchor="middle">
                {i + 1}
              </text>
            </g>
          );
        })}

        <path className="vintage-nav-line" d={navPath} />
        {navYears.map((v, i) => (
          <circle
            key={i}
            className="vintage-nav-marker"
            data-testid={`projection-nav-${sleeve}-${i}`}
            cx={cx(i)}
            cy={y(v)}
            r={3}
          >
            <title>{`year ${i + 1}: projected NAV ${v.toFixed(1)} (${usd(v)})`}</title>
          </circle>
        ))}
      </svg>
      <div className="vintage-chart-legend">
        <span className="vintage-chart-legend-item">
          <span className="vintage-chart-swatch vintage-chart-swatch-paid" /> Planned commitment
        </span>
        <span className="vintage-chart-legend-item">
          <span className="vintage-chart-swatch vintage-chart-swatch-nav" /> Projected NAV
        </span>
      </div>
    </div>
  );
}
