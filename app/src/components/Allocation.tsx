/**
 * The allocation panel — live feedback: "why would I de-risk unless I have
 * an idea of what my allocations are?"
 *
 * Mirrors the TARGET bookkeeping of ah.core.institution (START_MIX and the
 * shift rules) as pure arithmetic over the session's committed decisions.
 * Display-only: the server's institution sim remains the sole authority for
 * value and scoring. If institution.py's mix or shift rules change, this
 * mirror must change with them — a drift will show up as the reckoning
 * disagreeing with this panel, loudly.
 */

const START_MIX: Record<string, number> = {
  equity: 0.3,
  bonds: 0.1,
  hy: 0.05,
  commodities: 0.05,
  reits: 0.05,
  pe: 0.25,
  pc: 0.1,
  re: 0.1,
};

const GROWTH = ["equity", "pe"];
const DEFENSIVE = ["bonds", "pc"];
const SHIFT_PTS = 0.1;
const SECONDARY_TARGET_MOVE = 0.08;

const LABELS: Record<string, string> = {
  equity: "Equities",
  bonds: "Bonds",
  hy: "High yield",
  commodities: "Commodities",
  reits: "REITs",
  pe: "Private equity",
  pc: "Private credit",
  re: "Real estate",
};

function shift(
  t: Record<string, number>,
  frm: string[],
  to: string[],
  amount: number,
): void {
  const fsum = frm.reduce((s, k) => s + t[k], 0);
  const tsum = to.reduce((s, k) => s + t[k], 0);
  const amt = Math.min(amount, fsum);
  if (fsum <= 0 || tsum <= 0 || amt <= 0) return;
  for (const k of frm) t[k] -= amt * (t[k] / fsum);
  for (const k of to) t[k] += amt * (t[k] / tsum);
}

/** Replay the decision list over the target mix, exactly as the server will. */
export function replayTargets(decisions: Record<string, string>): Record<string, number> {
  const t = { ...START_MIX };
  const months = Object.keys(decisions)
    .map(Number)
    .sort((a, b) => a - b);
  for (const m of months) {
    const action = decisions[String(m)];
    if (action === "derisk") shift(t, GROWTH, DEFENSIVE, SHIFT_PTS);
    else if (action === "leanin") shift(t, DEFENSIVE, GROWTH, SHIFT_PTS);
    else if (action === "secondary") {
      const removed = Math.min(SECONDARY_TARGET_MOVE, t.pe);
      t.pe -= removed;
      t.bonds += removed;
      const total = Object.values(t).reduce((s, v) => s + v, 0);
      if (total > 0) for (const k of Object.keys(t)) t[k] /= total;
    }
  }
  return t;
}

export function Allocation({ decisions }: { decisions: Record<string, string> }) {
  const targets = replayTargets(decisions);
  const order = Object.keys(START_MIX);
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

  return (
    <section className="allocation" aria-label="target allocation">
      <h2>Your book</h2>
      <div className="alloc-bar" role="img" aria-label="target mix">
        {order.map((k) => (
          <span
            key={k}
            className={`alloc-seg alloc-${k}`}
            style={{ flexGrow: Math.max(targets[k], 0.001) }}
            title={`${LABELS[k]} ${pct(targets[k])}`}
          />
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>sleeve</th>
            <th>target</th>
            <th />
            <th>vs start</th>
          </tr>
        </thead>
        <tbody>
          {order.map((k) => {
            const d = targets[k] - START_MIX[k];
            const moved = Math.abs(d) > 1e-9;
            return (
              <tr key={k}>
                <td>
                  <span className={`alloc-dot alloc-${k}`} /> {LABELS[k]}
                  {GROWTH.includes(k) && <em className="alloc-group"> growth</em>}
                  {DEFENSIVE.includes(k) && <em className="alloc-group"> defensive</em>}
                </td>
                <td>{pct(targets[k])}</td>
                <td style={{ width: 90, paddingLeft: 12 }}>
                  <div className="alloc-bar" style={{ marginBottom: 0 }}>
                    <span
                      className={`alloc-seg alloc-${k}`}
                      style={{ flexGrow: 1, maxWidth: `${targets[k] * 100 * 3}%` }}
                    />
                  </div>
                </td>
                <td className={moved ? (d > 0 ? "ok" : "bad") : ""}>
                  {moved ? `${d > 0 ? "+" : "−"}${(Math.abs(d) * 100).toFixed(1)}pts` : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="alloc-note">
        Rebalanced to these targets at every yearly window. De-risk moves 10pts
        growth→defensive, lean in moves 10pts back, a secondary sale moves 8pts
        PE→bonds and takes an 18% haircut on the slice sold.
      </p>
    </section>
  );
}
