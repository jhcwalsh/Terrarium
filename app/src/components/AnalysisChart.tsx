/**
 * The analysis chart (su-app-04; register row E7).
 *
 * THREE series by design — player, policy twin, drift twin — with the layout,
 * legend, and colour set sized for three NOW, so the drift twin's arrival
 * (its engine work is scheduled later, DN-5 R-1) is a data arrival, not a
 * redesign. Renders correctly when given two; the legend marks the missing
 * series as pending rather than collapsing the slot.
 */

export interface AnalysisSeries {
  label: string;
  values: number[] | null; // null = slot reserved, data pending (drift twin)
  color: string;
}

export function threeSeries(
  player: number[],
  policyTwin: number[],
  driftTwin: number[] | null,
): AnalysisSeries[] {
  return [
    { label: "you", values: player, color: "#c62828" },
    { label: "policy twin", values: policyTwin, color: "#1565c0" },
    { label: "drift twin", values: driftTwin, color: "#6a1b9a" },
  ];
}

export function AnalysisChart({
  series,
  decisionMonths,
  width = 720,
  height = 280,
}: {
  series: AnalysisSeries[];
  decisionMonths: number[];
  width?: number;
  height?: number;
}) {
  const present = series.filter((s): s is AnalysisSeries & { values: number[] } =>
    Boolean(s.values),
  );
  const months = present[0]?.values.length ?? 0;
  let min = Infinity;
  let max = -Infinity;
  for (const s of present) {
    for (const v of s.values) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  const pad = (max - min) * 0.05 || 1;
  min -= pad;
  max += pad;
  const x = (m: number) => (m / Math.max(1, months - 1)) * width;
  const y = (v: number) => height - ((v - min) / (max - min)) * height;
  const line = (values: number[]) => values.map((v, m) => `${x(m)},${y(v)}`).join(" ");

  return (
    <figure className="analysis-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="analysis chart">
        {decisionMonths.map((m) => (
          <line
            key={m}
            x1={x(m)}
            y1={0}
            x2={x(m)}
            y2={height}
            className="analysis-window-line"
          />
        ))}
        {present.map((s) => (
          <polyline
            key={s.label}
            points={line(s.values)}
            fill="none"
            stroke={s.color}
            strokeWidth={s.label === "you" ? 2 : 1.5}
          />
        ))}
      </svg>
      <figcaption className="analysis-legend">
        {series.map((s) => (
          <span key={s.label} style={{ color: s.color }}>
            ● {s.label}
            {s.values === null ? " (pending)" : ""}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
