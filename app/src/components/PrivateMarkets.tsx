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

interface LadderBar {
  id: string;
  nav: number;
  /** height against the LARGEST rung, so the staircase's shape is readable */
  share: number;
}

interface LadderSummary {
  count: number;
  total: number;
  bars: LadderBar[];
}

/** The ladder as a bar strip rather than a row per cohort (ladder-01).
 *
 *  The opening book is a staggered ladder — one vintage per year of a fund's
 *  life, so 30 rungs at open and 57 by the end of a decade. The vitrine is
 *  pinned to one screen, and 57 text rows is not one screen. Bars scale to any
 *  count; the count and total carry the numbers, and each bar keeps its own
 *  id and NAV in a title so nothing is actually hidden. */
export function ladderSummary(
  vintageNav: Record<string, number> | null | undefined,
): LadderSummary | null {
  if (!vintageNav) return null;
  const entries = Object.entries(vintageNav);
  if (entries.length === 0) return null;
  entries.sort(([a], [b]) => a.localeCompare(b));
  const largest = Math.max(...entries.map(([, nav]) => nav));
  return {
    count: entries.length,
    total: entries.reduce((sum, [, nav]) => sum + nav, 0),
    bars: entries.map(([id, nav]) => ({
      id,
      nav,
      share: largest > 0 ? nav / largest : 0,
    })),
  };
}

interface ExpiredCommitment {
  /** released this quarter — usually 0 */
  quarter: number;
  /** released so far this decade — what keeps the event on the page */
  toDate: number;
  justHappened: boolean;
}

/** Undrawn commitment CANCELLED at the end of a fund's contractual life
 *  (ER-6's visible lapse; surfaced by audit F2). Session-only: the twin
 *  ledger in the bundle carries no such series, and showing the twin's as
 *  though it were the player's is exactly what `pickLedgerRow` exists to
 *  prevent. Null means there is nothing to say — no session, nothing
 *  expired yet, or the quarter is not revealed. */
export function expiredCommitment(
  session: { expired_undrawn?: number | null; expired_undrawn_to_date?: number | null } | null,
): ExpiredCommitment | null {
  if (!session) return null;
  const toDate = session.expired_undrawn_to_date;
  if (toDate == null || toDate <= 0) return null;
  const quarter = session.expired_undrawn ?? 0;
  return { quarter, toDate, justHappened: quarter > 0 };
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
  const expired = expiredCommitment(session);
  const ladder = ladderSummary(session?.vintage_nav);

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
      {expired && (
        <p className={expired.justHappened ? "privates-expired now" : "privates-expired"}>
          {expired.justHappened
            ? `commitment expired this quarter: ${n2(expired.quarter)}`
            : `commitment expired to date: ${n2(expired.toDate)}`}
          <span className="privates-note">
            {" "}
            — undrawn capital released at the end of a fund's life. It leaves your unfunded
            total without ever being called, so you will never pay it.
          </span>
        </p>
      )}
      {session?.trailing_distributions && session.trailing_distributions.length > 0 && (
        <p className="privates-trailing">
          trailing distributions:{" "}
          {session.trailing_distributions.map((v) => v.toFixed(2)).join(" · ")}
        </p>
      )}
      {ladder && (
        <div className="vintage-stack" aria-label="vintage stack by age">
          <span className="stack-title">
            the ladder — {ladder.count} vintages, {n2(ladder.total)} NAV
          </span>
          <div className="stack-bars">
            {ladder.bars.map((bar) => (
              <i
                key={bar.id}
                style={{ height: `${Math.max(2, bar.share * 100)}%` }}
                title={`${bar.id}: ${n2(bar.nav)}`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
