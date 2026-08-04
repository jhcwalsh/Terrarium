/**
 * The fan chart (su-app-01; DN-3 W3): the ensemble's percentile cone with the
 * revealed path drawn over it, clipped at the reveal pointer.
 *
 * Hand-rolled SVG — no chart library. The cone is two stacked band polygons
 * (p5–p95, p25–p75) plus the median line; the revealed path draws only up to
 * `revealedMonths`, because the future does not exist yet for the player.
 */

interface FanChartProps {
  /** percentile name -> cumulative growth series, from bundle.bands[asset] */
  bands: Record<string, number[]>;
  /** the revealed path's cumulative growth series (full horizon) */
  revealed: number[];
  revealedMonths: number;
  width?: number;
  height?: number;
  label?: string;
}

function scale(
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

export function FanChart({
  bands,
  revealed,
  revealedMonths,
  width = 720,
  height = 260,
  label,
}: FanChartProps) {
  const months = revealed.length;
  const { min, max } = scale(bands, revealed, revealedMonths);
  const x = (m: number) => (m / Math.max(1, months - 1)) * width;
  const y = (v: number) => height - ((v - min) / (max - min)) * height;

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

  return (
    <figure className="fan-chart">
      {label && <figcaption>{label}</figcaption>}
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label ?? "fan chart"}>
        <polygon points={band(bands.p5, bands.p95)} className="fan-outer" />
        <polygon points={band(bands.p25, bands.p75)} className="fan-inner" />
        <polyline points={line(bands.p50, months)} className="fan-median" fill="none" />
        {revealedMonths > 0 && (
          <polyline points={line(revealed, revealedMonths)} className="fan-revealed" fill="none" />
        )}
        {revealedMonths > 0 && revealedMonths < months && (
          <line
            x1={x(revealedMonths - 1)}
            y1={0}
            x2={x(revealedMonths - 1)}
            y2={height}
            className="fan-pointer"
          />
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
