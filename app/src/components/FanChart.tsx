/**
 * The fan chart (su-app-01; DN-3 W3): the ensemble's percentile cone with the
 * revealed path drawn over it, clipped at the reveal pointer.
 *
 * Hand-rolled SVG — no chart library. The cone is two stacked band polygons
 * (p5–p95, p25–p75) plus the median line; the revealed path draws only up to
 * `revealedMonths`, because the future does not exist yet for the player.
 *
 * Axes and the current-value marker were added after the first live play:
 * a cone with no scale reads as decoration, not information. Everything is
 * on the growth-of-1 scale — ×1.40 means 1 invested at t0 is now 1.40.
 * The unrevealed region is drawn as a hatched SEALED zone (vitrine remodel):
 * the future is not blank, it is withheld.
 */

import { useId } from "react";

interface FanChartProps {
  /** percentile name -> cumulative growth series, from bundle.bands[asset] */
  bands: Record<string, number[]>;
  /** the revealed path's cumulative growth series (full horizon) */
  revealed: number[];
  revealedMonths: number;
  width?: number;
  height?: number;
  label?: string;
  className?: string;
}

// plot margins: room for the ×-scale on the left, year marks below
const ML = 48;
const MR = 12;
const MT = 8;
const MB = 20;

function extent(
  bands: Record<string, number[]>,
  revealed: number[],
  revealedMonths: number,
): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const series of Object.values(bands)) {
    for (const v of series) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  for (let m = 0; m < revealedMonths; m++) {
    const v = revealed[m];
    if (v < min) min = v;
    if (v > max) max = v;
  }
  const pad = (max - min) * 0.05 || 0.1;
  return { min: min - pad, max: max + pad };
}

/** A handful of round tick values inside [min, max]. */
function ticks(min: number, max: number): number[] {
  const span = max - min;
  if (!(span > 0)) return [];
  const mag = 10 ** Math.floor(Math.log10(span / 4));
  const step =
    [1, 2, 2.5, 5, 10].map((s) => s * mag).find((s) => span / s <= 5) ?? 10 * mag;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-6; v += step) {
    out.push(Number(v.toFixed(6)));
  }
  return out;
}

const fmt = (v: number) => `×${v >= 10 ? v.toFixed(1) : v.toFixed(2)}`;

export function FanChart({
  bands,
  revealed,
  revealedMonths,
  width = 720,
  height = 240,
  label,
  className,
}: FanChartProps) {
  const sealId = useId();
  const months = revealed.length;
  const { min, max } = extent(bands, revealed, revealedMonths);
  const plotW = width - ML - MR;
  const plotH = height - MT - MB;
  const x = (m: number) => ML + (m / Math.max(1, months - 1)) * plotW;
  const y = (v: number) => MT + plotH - ((v - min) / (max - min)) * plotH;

  const band = (lo: number[], hi: number[]) => {
    const up = lo.map((v, m) => `${x(m)},${y(v)}`);
    const down = hi.map((v, m) => `${x(m)},${y(v)}`).reverse();
    return `${up.join(" ")} ${down.join(" ")}`;
  };
  const line = (series: number[], upTo: number) =>
    series
      .slice(0, upTo)
      .map((v, m) => `${x(m)},${y(v)}`)
      .join(" ");

  const yTicks = ticks(min, max);
  const yearMarks: number[] = [];
  for (let yr = 2; yr * 12 <= months; yr += 2) yearMarks.push(yr);
  const now = revealedMonths > 0 ? revealed[revealedMonths - 1] : null;

  const sealX = revealedMonths > 0 ? x(revealedMonths - 1) : ML;
  const sealW = width - MR - sealX;

  return (
    <figure className={`fan-chart${className ? ` ${className}` : ""}`}>
      {label && (
        <figcaption>
          {label}
          {now !== null && <span className="fan-now">{fmt(now)}</span>}
        </figcaption>
      )}
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label ?? "fan chart"}>
        <defs>
          <pattern
            id={sealId}
            width="7"
            height="7"
            patternTransform="rotate(45)"
            patternUnits="userSpaceOnUse"
          >
            <line x1="0" y1="0" x2="0" y2="7" stroke="#153035" strokeWidth="3" />
          </pattern>
        </defs>
        {revealedMonths < months && sealW > 0 && (
          <g>
            <rect
              x={sealX}
              y={MT}
              width={sealW}
              height={plotH}
              fill={`url(#${sealId})`}
              className="fan-seal"
            />
            {sealW > 90 && (
              <text x={sealX + 12} y={MT + 14} className="fan-seal-text">
                SEALED
              </text>
            )}
          </g>
        )}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={ML}
              y1={y(v)}
              x2={width - MR}
              y2={y(v)}
              className={v === 1 ? "fan-baseline" : "fan-grid"}
            />
            <text x={ML - 5} y={y(v) + 3} className="fan-tick" textAnchor="end">
              {fmt(v)}
            </text>
          </g>
        ))}
        {yearMarks.map((yr) => (
          <text
            key={yr}
            x={x(yr * 12 - 1)}
            y={height - 6}
            className="fan-tick"
            textAnchor="middle"
          >
            Y{yr}
          </text>
        ))}
        <polygon points={band(bands.p5, bands.p95)} className="fan-outer" />
        <polygon points={band(bands.p25, bands.p75)} className="fan-inner" />
        <polyline points={line(bands.p50, months)} className="fan-median" fill="none" />
        {revealedMonths > 0 && (
          <polyline points={line(revealed, revealedMonths)} className="fan-revealed" fill="none" />
        )}
        {revealedMonths > 0 && revealedMonths < months && (
          <line
            x1={x(revealedMonths - 1)}
            y1={MT}
            x2={x(revealedMonths - 1)}
            y2={MT + plotH}
            className="fan-pointer"
          />
        )}
        {now !== null && (
          <circle cx={x(revealedMonths - 1)} cy={y(now)} r={3} className="fan-now-dot" />
        )}
      </svg>
    </figure>
  );
}

/** Cumulative growth of 1 from a monthly percent-return column. */
export function cumulativeGrowth(returnsPct: number[]): number[] {
  const out = new Array<number>(returnsPct.length);
  let acc = 1;
  for (let m = 0; m < returnsPct.length; m++) {
    acc *= 1 + returnsPct[m] / 100;
    out[m] = acc;
  }
  return out;
}
