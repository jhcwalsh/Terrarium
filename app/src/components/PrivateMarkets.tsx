/**
 * The private-markets ledger (owner: "we need to be able to look at the
 * commitments, calls and distributions for each of the private assets —
 * these, with the payout and returns will drive actions such as secondary
 * sales").
 *
 * Reads the pacing ledger the bundle carries, revealed with the pointer like
 * everything else: a quarter's row exists for the player only once its month
 * is on the tape.
 *
 * INFORMATIONAL. The engine has no cash account, so these calls are not
 * funded from anywhere and cannot force a sale — binding them to the
 * portfolio is Step 3's institutional twin (register ER-3). The panel says so
 * on its face, because a player who believes this money is moving is being
 * misled.
 */

import type { PrivateLedger } from "../lib/bundle";

const LABELS: Record<string, string> = {
  pe: "Private equity",
  pc: "Private credit",
  re: "Real estate",
};

/** The last quarter whose closing month has been revealed, or -1. */
export function lastRevealedQuarter(quarterMonths: number[], revealedMonths: number): number {
  let idx = -1;
  for (let q = 0; q < quarterMonths.length; q++) {
    if (quarterMonths[q] < revealedMonths) idx = q;
  }
  return idx;
}

const n1 = (v: number) => v.toFixed(1);
const n2 = (v: number) => v.toFixed(2);

export function PrivateMarkets({
  ledgers,
  revealedMonths,
}: {
  ledgers: Record<string, PrivateLedger>;
  revealedMonths: number;
}) {
  const keys = Object.keys(LABELS).filter((k) => ledgers[k]);
  if (keys.length === 0) return null;

  return (
    <div className="privates" aria-label="private markets ledger">
      <table>
        <thead>
          <tr>
            <th>programme</th>
            <th>commit</th>
            <th>unfunded</th>
            <th>called qtr</th>
            <th>dist qtr</th>
            <th>NAV</th>
            <th>DPI</th>
            <th>TVPI</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const l = ledgers[k];
            const q = lastRevealedQuarter(l.quarter_months, revealedMonths);
            const at = (xs: number[]) => (q >= 0 ? xs[q] : 0);
            return (
              <tr key={k}>
                <td>
                  <span className={`alloc-dot alloc-${k}`} /> {LABELS[k]}
                </td>
                <td>{n1(l.commitment)}</td>
                <td>{q >= 0 ? n1(at(l.unfunded)) : n1(l.commitment)}</td>
                <td className={at(l.called) > 0 ? "call" : ""}>
                  {q >= 0 ? n2(at(l.called)) : "—"}
                </td>
                <td className={at(l.distributed) > 0 ? "dist" : ""}>
                  {q >= 0 && at(l.distributed) > 0 ? n2(at(l.distributed)) : "—"}
                </td>
                <td>{q >= 0 ? n1(at(l.nav)) : "—"}</td>
                <td>{q >= 0 ? n2(at(l.dpi)) : "—"}</td>
                <td>{q >= 0 ? n2(at(l.tvpi)) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="privates-note">
        Points of the starting book. Commitments run at 1.5x target — capital
        comes back before it is all drawn. Informational: the toy engine has no
        cash account, so calls are not funded and cannot force a sale.
      </p>
    </div>
  );
}
