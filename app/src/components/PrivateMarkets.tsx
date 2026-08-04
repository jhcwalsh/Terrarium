/**
 * The private-markets ledger (owner: "we need to be able to look at the
 * commitments, calls and distributions for each of the private assets —
 * these, with the payout and returns will drive actions such as secondary
 * sales").
 *
 * Reads the hold-course twin's ledger the bundle carries (world-bundle-0.4,
 * `TwinLedger`), revealed with the pointer like everything else: a quarter's
 * row exists only once its closing month is on the tape.
 *
 * Once a session exists, the player's OWN numbers for the current quarter
 * win over the twin's — `pickLedgerRow` is the one place that decision is
 * made, and it always labels which book a number came from. The twin's
 * ledger is decision-independent and ships in the bundle, so it is what
 * browse mode and offline replay (no session) fall back to; it must never
 * be shown as if it were the player's.
 */

import type { TwinLedger } from "../lib/bundle";
import type { Session } from "../lib/session";

/** The last quarter whose closing month has been revealed, or -1. */
export function lastRevealedQuarter(quarterMonths: number[], revealedMonths: number): number {
  let idx = -1;
  for (let q = 0; q < quarterMonths.length; q++) {
    if (quarterMonths[q] < revealedMonths) idx = q;
  }
  return idx;
}

interface LedgerRow {
  calls: number;
  distributions: number;
  source: "yours" | "twin";
}

/** The player's own numbers when a session exists; the twin's otherwise.
 *  Browse mode and offline replay (W8) both land on the twin, which is the
 *  honest thing to show when nobody has made a decision yet. */
export function pickLedgerRow(
  twin: { calls: number[]; distributions: number[] } | undefined,
  session: { calls_paid?: number | null; distributions_received?: number | null } | null,
  quarter: number,
): LedgerRow | null {
  if (session && session.calls_paid != null && session.distributions_received != null) {
    return {
      calls: session.calls_paid,
      distributions: session.distributions_received,
      source: "yours",
    };
  }
  if (twin && quarter >= 0 && quarter < twin.calls.length) {
    return {
      calls: twin.calls[quarter],
      distributions: twin.distributions[quarter],
      source: "twin",
    };
  }
  return null;
}

const SOURCE_LABEL: Record<LedgerRow["source"], string> = {
  yours: "your book",
  twin: "hold-course twin",
};

const n2 = (v: number) => v.toFixed(2);

export function PrivateMarkets({
  ledger,
  session,
  revealedMonths,
}: {
  ledger?: TwinLedger;
  session: Session | null;
  revealedMonths: number;
}) {
  const quarter = ledger ? lastRevealedQuarter(ledger.quarter_months, revealedMonths) : -1;
  const row = pickLedgerRow(ledger, session, quarter);

  if (!row) {
    return (
      <div className="privates" aria-label="private markets ledger">
        <p className="privates-note">Nothing yet — advance time.</p>
      </div>
    );
  }

  return (
    <div className="privates" aria-label="private markets ledger">
      <table>
        <thead>
          <tr>
            <th>called qtr</th>
            <th>dist qtr</th>
            <th>source</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className={row.calls > 0 ? "call" : ""}>{n2(row.calls)}</td>
            <td className={row.distributions > 0 ? "dist" : ""}>
              {row.distributions > 0 ? n2(row.distributions) : "—"}
            </td>
            <td>{SOURCE_LABEL[row.source]}</td>
          </tr>
        </tbody>
      </table>
      <p className="privates-note">
        {row.source === "twin"
          ? "No session yet — these are the hold-course twin's cashflows, not yours."
          : "Your book's calls and distributions for the quarter just closed."}
      </p>
    </div>
  );
}
