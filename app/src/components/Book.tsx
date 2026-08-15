/**
 * The book — what the institution actually holds, on the real twin.
 *
 * Replaces the target-mix table. Under ah.play, targets are not the mechanic:
 * private cohorts are not dials, so a mirror of "targets" would describe a
 * machine that no longer exists. What matters now is the book itself — cash,
 * coverage, and whether the private weight is inside the policy band.
 *
 * Every number here is computed SERVER-SIDE (DN-3 W5). This renders; it does
 * not calculate.
 */

import type { Session } from "../lib/session";

/** ah.port.engine.Policy.private_weight_range, mirrored for display only. */
export const PRIVATE_BAND: [number, number] = [0.15, 0.4];

const pct = (v: number | null | undefined, dp = 1) =>
  v == null ? "—" : `${(v * 100).toFixed(dp)}%`;
const num = (v: number | null | undefined, dp = 1) =>
  v == null ? "—" : v.toFixed(dp);

export function Book({ session }: { session: Session }) {
  const pw = session.private_weight_true;
  const [lo, hi] = PRIVATE_BAND;
  const breached = pw != null && (pw < lo || pw > hi);

  return (
    <div className="book" aria-label="the book">
      <div className="book-rail">
        <div>
          {/* Value is session.value, computed server-side on this session's
              FIXED scoring basis (doc["basis"]) — the CIO dashboard's own
              value follows the live plane toggle instead, so the two panels
              can legitimately disagree in CIO mode. Label it so a reader
              never has to guess which number is which. */}
          <span className="k">Value &middot; {session.basis} basis</span>
          <span className="v">{num(session.value)}</span>
        </div>
        <div>
          <span className="k">Cash</span>
          <span className={`v${session.cash != null && session.cash <= 0.01 ? " tight" : ""}`}>
            {num(session.cash, 2)}
          </span>
        </div>
        <div>
          {/* coverage_true is unconditionally true-basis, independent of
              session.basis and of any plane toggle — labelled for the same
              reason as Value above. */}
          <span className="k">Coverage &middot; true basis</span>
          <span className="v">{pct(session.coverage_true)}</span>
        </div>
      </div>

      <table>
        <tbody>
          <tr>
            <td>Private weight &middot; true basis</td>
            <td>{pct(pw)}</td>
            <td className={breached ? "band-breach" : "band-ok"}>
              {breached ? "outside" : "inside"} {pct(lo, 0)}–{pct(hi, 0)}
            </td>
          </tr>
          <tr>
            <td>Called this quarter</td>
            <td>{num(session.calls_paid, 2)}</td>
            <td />
          </tr>
          <tr>
            <td>Distributions</td>
            <td>{num(session.distributions_received, 2)}</td>
            <td />
          </tr>
          <tr>
            <td>Spending</td>
            <td>{num(session.spending_paid, 2)}</td>
            <td />
          </tr>
        </tbody>
      </table>

      <p className="book-note">
        Coverage is unfunded commitments over assets. On reported marks it reads{" "}
        {pct(session.coverage_reported)} against {pct(session.coverage_true)} true —
        the denominator gap that makes a book look healthiest exactly when it is
        not.
      </p>
    </div>
  );
}
