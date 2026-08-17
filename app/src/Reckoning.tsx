/**
 * The reckoning (su-app-04): outcome card, three-series analysis, and the
 * chess-style post-game review.
 *
 * - Outcome card (E3): the headline numbers plus the interpretation guide's
 *   framing. Toy-plane scope stated in the card: forced-sale counts and
 *   coverage-on-both-bases join when Step-3 engine paths power the product
 *   plane (the register row's engine side is done; this surface reserves
 *   the slots).
 * - Analysis (E7): the three-series chart — player, policy twin, drift twin
 *   (slot reserved, data pending).
 * - Review (E4/E8): step through the decade window by window; each window
 *   carries its one-line annotation from the chain-link decomposition
 *   (`Year 4, de-risked: -2.1 points`) — the tone rule is the style
 *   guide's: state the number, never gloat.
 */

import { useState } from "react";
import { AnalysisChart, threeSeries } from "./components/AnalysisChart";
import { usd } from "./lib/money";
import type { Outcome } from "./lib/session";

const ACTION_PHRASE: Record<string, string> = {
  hold: "held course",
  derisk: "de-risked",
  leanin: "leaned in",
  secondary: "sold a secondary",
};

export function annotationLine(w: { month: number; action: string; contribution: number }) {
  const year = Math.floor((w.month + 1) / 12);
  const phrase = ACTION_PHRASE[w.action] ?? w.action;
  const pts = `${w.contribution >= 0 ? "+" : ""}${w.contribution.toFixed(1)} points`;
  // app-open-01 item 2 (owner ruling 2026-08-16): the per-window
  // chain-link contribution is the scored truth in points; the dollar
  // figure (money.ts usd()) rides alongside, never in place of it.
  return `Year ${year}, ${phrase}: ${pts} / ${usd(w.contribution)}`;
}

export function Reckoning({
  outcome,
  onExit,
  board,
}: {
  outcome: Outcome;
  onExit: () => void;
  board?: React.ReactNode;
}) {
  const [reviewIdx, setReviewIdx] = useState<number | null>(null);
  const series = outcome.series
    ? threeSeries(outcome.series.active, outcome.series.twin, outcome.series.drift_twin)
    : null;

  return (
    <main className="shell">
      <section className="outcome-card">
        <h1>The reckoning</h1>
        <div className="outcome-headline">
          {/* app-open-01 item 1 (owner ruling 2026-08-16): final book VALUES
              get the $10bn display denomination outright — final_value and
              twin_final_value themselves are untouched, still the scored
              points the server returned. */}
          <div>
            <span className="outcome-label">you</span>
            <strong>{usd(outcome.final_value)}</strong>
          </div>
          <div>
            <span className="outcome-label">policy twin</span>
            <strong>{usd(outcome.twin_final_value)}</strong>
          </div>
          <div>
            <span className="outcome-label">decision alpha</span>
            {/* alpha is an index, not a value: points stay the headline
                figure (the scored truth) and the dollar equivalent rides
                alongside, never in place of it. */}
            <strong className={outcome.alpha >= 0 ? "ok" : "bad"}>
              {outcome.alpha >= 0 ? "+" : ""}
              {outcome.alpha.toFixed(2)}
            </strong>
            <span className="outcome-alpha-usd">{usd(outcome.alpha)}</span>
          </div>
        </div>
        <p className="outcome-note">
          Alpha is your final value minus the policy twin — same world, same
          shocks, only the decisions differ. The twin paces its commitments to
          policy and never sells by choice; forced secondaries this run:{" "}
          {outcome.forced_secondaries}.
        </p>
      </section>

      {series && (
        <AnalysisChart
          series={series}
          // outcome.series is one point per closed QUARTER (not month), so the
          // decision-window markers must be converted from month index to
          // quarter index before they're handed to the chart's x-scale.
          decisionMonths={outcome.windows.map((w) => Math.floor(w.month / 3))}
        />
      )}

      <section className="review" aria-label="post-game review">
        <h2>The review</h2>
        <ol className="review-lines">
          {outcome.windows.map((w, i) => (
            <li
              key={w.month}
              className={reviewIdx === i ? "selected" : ""}
              onClick={() => setReviewIdx(i)}
            >
              {annotationLine(w)}
            </li>
          ))}
        </ol>
        {reviewIdx !== null && (
          <p className="review-detail">
            {annotationLine(outcome.windows[reviewIdx])} — this is the value of the
            decision given everything decided before it and mechanical policy
            after it (the chain-link convention; the lines sum exactly to your
            alpha).
          </p>
        )}
        {(outcome.annotations?.length ?? 0) > 0 && (
          <div className="review-annotations" aria-label="annotations">
            <h3>Two things the numbers noticed</h3>
            <ul>
              {outcome.annotations!.map((a) => (
                <li key={`${a.type}-${a.month}`} className={`note-${a.type}`}>
                  {a.text}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {board}

      <button onClick={onExit}>back to browse</button>
    </main>
  );
}
