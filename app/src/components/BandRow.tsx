/**
 * su-app-07 task 4b / app-open-02: one banded sleeve's status, as the server
 * judged it. Shared by `BandPanel` (Play.tsx, between decision windows) and
 * the open-window band strip (`DecisionWindow`) so this markup exists in
 * exactly one place — see both callers' docstrings for why the discipline
 * below matters.
 *
 * NEVER recomputes `alert` (DN-3 W5): `row[plane]` is read straight off the
 * served document and printed verbatim — the server judges on unrounded
 * weights while serving them rounded to 4dp, so a client re-running the rule
 * can legitimately disagree exactly at a band edge, the one place it
 * matters. `plane` is taken as given; this component does not call
 * `planeForBasis` itself, so it cannot pick the wrong one by accident — the
 * caller does, once, the same way every time.
 */
import type { Plane } from "../lib/cioView";
import { labelFor } from "../lib/assetLabels";
import type { BandSleeve } from "../lib/session";

export function BandRow({
  row,
  plane,
  compact = false,
}: {
  row: BandSleeve;
  plane: Plane;
  /** Drops the "target NN.N ·" prefix for the open-window strip, which sits
   * directly above the four action cards and has no room to spare. The
   * between-window panel (BandPanel) leaves this false, so its DOM is
   * unchanged by this extraction. */
  compact?: boolean;
}) {
  const here = row[plane];
  const name = labelFor(row.sleeve);
  return (
    <li className={`band-cell alert-${here.alert}`} data-sleeve={row.sleeve}>
      <div className="band-head">
        <span className="band-name">{name}</span>
        <span className="band-badge">{here.alert}</span>
      </div>
      <div className="band-nums">
        <span className="band-weight">{here.weight.toFixed(1)}</span>
        <span className="band-range">
          {compact ? null : (
            <>target {row.target.toFixed(1)} &middot; </>
          )}
          band {row.lo.toFixed(1)}–{row.hi.toFixed(1)}
        </span>
      </div>
    </li>
  );
}
