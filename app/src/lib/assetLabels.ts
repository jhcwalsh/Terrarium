/**
 * Display order + names for every asset the bundle carries bands for. The
 * engine's contract order, not the JSON's alphabetical key order.
 *
 * Extracted out of Play.tsx (app-open-02) so it can be shared with
 * `components/BandRow.tsx` without a circular import: Play.tsx imports
 * `DecisionWindow`, so `DecisionWindow`/`BandRow` importing anything back out
 * of `Play.tsx` would cycle. Play.tsx re-exports `ASSET_LABELS` from here so
 * its existing external consumer (App.tsx: `import { ASSET_LABELS } from
 * "./Play"`) is untouched.
 */
export const ASSET_LABELS: ReadonlyArray<readonly [string, string]> = [
  ["equity", "Equities"],
  ["bonds", "Bonds"],
  ["hy", "High yield"],
  ["commodities", "Commodities"],
  ["reits", "REITs"],
  ["pe", "Private equity"],
  ["pc", "Private credit"],
  ["re", "Real estate"],
  ["infra", "Infrastructure"],
];

/** The display name for a sleeve key, falling back to the raw key for
 * anything `ASSET_LABELS` does not know (a band report names sleeves the
 * server judged, not a fixed set this list is required to cover). */
export function labelFor(sleeve: string): string {
  return ASSET_LABELS.find(([key]) => key === sleeve)?.[1] ?? sleeve;
}
