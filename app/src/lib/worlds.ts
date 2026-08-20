/**
 * sib-01: the "choose your decade" landing list.
 *
 * `/worlds` (Task 1) lists every world the store holds, each with its runs
 * newest-first. This module is a thin typed fetch + shape-check over that
 * endpoint, plus the presentational list itself — a picker of run buttons
 * that feed `bundleUrlFor(run_id)` into the SAME URL loader App.tsx already
 * uses for manual bundle URLs (`fetchBundle`, in `bundle.ts`). Seal
 * verification and caching stay entirely in that existing path; this module
 * never touches bundle bytes.
 *
 * Progressive enhancement, not a dependency: any failure here (service down,
 * static hosting with no `/worlds`, a malformed document) is caught by the
 * caller and the landing falls back to exactly the picker/URL flow that
 * existed before this module — `WorldPicker` renders nothing when handed a
 * null doc.
 *
 * `WorldPicker` is written with `createElement` rather than JSX so this can
 * stay a `.ts` file alongside its `.ts` test, following the `FanChart.tsx` /
 * `FanChart.test.ts` split already in this tree.
 */

import { createElement, type ReactElement } from "react";

export interface WorldRun {
  run_id: string;
  seed: number;
  created_at: string;
}

export interface WorldEntry {
  world_id: string;
  title: string | null;
  generator_id: string | null;
  /**
   * Chosen-PE fix round (2026-08-20): the SERVER-authoritative retirement
   * fence (`ah.retired_worlds.RETIRED_WORLD_IDS`, surfaced by `/worlds`).
   * A retired world is a readable record of an earlier engine/equation
   * release and must never be selectable for new play. Optional so a doc
   * from an older server (or a static host) still parses — absent means
   * "not marked retired", which matches that server's own behavior.
   */
  retired?: boolean;
  runs: WorldRun[];
}

export interface WorldsDoc {
  worlds: WorldEntry[];
}

export class WorldsFormatError extends Error {}

function isWorldRun(x: unknown): x is WorldRun {
  if (typeof x !== "object" || x === null) return false;
  const r = x as Record<string, unknown>;
  return (
    typeof r.run_id === "string" &&
    typeof r.seed === "number" &&
    typeof r.created_at === "string"
  );
}

function isWorldEntry(x: unknown): x is WorldEntry {
  if (typeof x !== "object" || x === null) return false;
  const e = x as Record<string, unknown>;
  return (
    typeof e.world_id === "string" &&
    (e.title === null || typeof e.title === "string") &&
    (e.generator_id === null || typeof e.generator_id === "string") &&
    (e.retired === undefined || typeof e.retired === "boolean") &&
    Array.isArray(e.runs) &&
    e.runs.every(isWorldRun)
  );
}

function isWorldsDoc(x: unknown): x is WorldsDoc {
  if (typeof x !== "object" || x === null) return false;
  const d = x as Record<string, unknown>;
  return Array.isArray(d.worlds) && d.worlds.every(isWorldEntry);
}

/**
 * app-open-01 (owner ruling, 2026-08-16): the opening "Choose your decade"
 * list showed three generations of worlds at once — toy-engine
 * ("The Long Stagflation" family, `generator_id: "toy-v0"`), plain bootstrap
 * ("Nineteen Seventy-Four" family, `"bootstrap-v1"`), and declared-stress
 * ("The Long Squeeze", "The Lost Decade", `"bootstrap-stratified"` — the
 * stress-scenario compiler's dispatcher id, see `ah/gen/stress.py`). The
 * owner wants only the declared-stress generation shown here. This is a
 * DISPLAY filter only: the server keeps listing every world (`/worlds`,
 * `src/ah/serve.py::list_worlds`, deliberately unfiltered), the stores keep
 * every world, and `fetchWorlds`/`WorldsDoc` are untouched — re-admitting a
 * generation later is adding its id to this list.
 */
export const SHOWN_GENERATOR_IDS: readonly string[] = ["bootstrap-stratified"];

/**
 * app-open-01 review round fix 2 (owner ruling 2026-08-16): world_ids the
 * store still holds but whose methodology is retired.
 *
 * 702 is The Lost Decade at 18-month blocks, superseded by 703 (6-month
 * blocks, the 2026-08-15 declaration); owner ruling 2026-08-16: worlds on
 * retired methodology are hidden, never deleted.
 */
export const HIDDEN_WORLD_IDS: readonly string[] = [
  "00000000-0000-4000-9000-000000000702",
];

/** The single newest run for a world, by `created_at`. */
function newestRun(world: WorldEntry): WorldRun | null {
  let best: WorldRun | null = null;
  for (const run of world.runs) {
    if (best === null || run.created_at > best.created_at) best = run;
  }
  return best;
}

/**
 * The worlds this picker renders: `SHOWN_GENERATOR_IDS` only, with
 * server-flagged retired worlds and `HIDDEN_WORLD_IDS` fenced out. Worlds
 * with no runs are dropped, since there is nothing for their button to open.
 *
 * Chosen-PE fix round (2026-08-20): `world.retired` is the server's own
 * fence (see `WorldEntry.retired`) — without it the picker showed retired
 * generated worlds beside their successors under duplicate titles, and a
 * player could open a world whose stored run the current equation no longer
 * reproduces. `HIDDEN_WORLD_IDS` stays what it always was: the one
 * client-side hide (702) that predates the server fence.
 *
 * app-open-01 review round fix 2: the real duplicate is TWO DIFFERENT
 * world_ids — 702 and 703 — sharing the display title "The Lost Decade",
 * which is why a player saw it twice. The `/worlds` document lists each
 * world_id once (one `WorldEntry` per world, `runs` nested inside it), so
 * there was never a same-`world_id` collision to dedupe here; a prior
 * version of this function carried an unreachable Map-based dedupe built
 * on that false premise. The fix for a title collision is naming which
 * world_id to hide (`HIDDEN_WORLD_IDS`), not deduping by world_id.
 */
export function selectShownWorlds(worlds: WorldEntry[]): WorldEntry[] {
  return worlds.filter(
    (world) =>
      !!world.generator_id &&
      SHOWN_GENERATOR_IDS.includes(world.generator_id) &&
      world.retired !== true &&
      !HIDDEN_WORLD_IDS.includes(world.world_id) &&
      world.runs.length > 0,
  );
}

/** Fetches and shape-checks the decade picker's data. Throws
 * `WorldsFormatError` on a non-ok response or a malformed document —
 * callers treat both as "no list", never as a fatal error. */
export async function fetchWorlds(): Promise<WorldsDoc> {
  const res = await fetch("/worlds");
  if (!res.ok) throw new WorldsFormatError(`fetch /worlds: ${res.status}`);
  const doc: unknown = await res.json();
  if (!isWorldsDoc(doc)) throw new WorldsFormatError("malformed /worlds document");
  return doc;
}

/** The bundle URL for a run, fed straight into the existing `fetchBundle`
 * URL loader — the same path manual URL entry already uses. */
export function bundleUrlFor(runId: string): string {
  return `/runs/${runId}/bundle`;
}

/** The "Choose your decade" list: one load button per shown world
 * (`selectShownWorlds` — declared-stress only, `HIDDEN_WORLD_IDS` fenced
 * out), wired to that world's newest run. Renders nothing when there is no
 * doc or nothing survives the filter — `fetchWorlds` failed, hasn't
 * resolved yet, the store has no worlds, or none of them are
 * declared-stress — so the landing view falls back to exactly the
 * picker/URL flow that already existed. */
export function WorldPicker({
  doc,
  onOpen,
}: {
  doc: WorldsDoc | null;
  onOpen: (url: string) => void;
}): ReactElement | null {
  if (!doc) return null;
  const shown = selectShownWorlds(doc.worlds);
  if (shown.length === 0) return null;
  return createElement(
    "section",
    { className: "world-picker" },
    createElement("h2", null, "Choose your decade"),
    createElement(
      "ul",
      null,
      ...shown.map((world) => {
        const run = newestRun(world)!; // selectShownWorlds already dropped worlds with no runs
        return createElement(
          "li",
          { key: world.world_id },
          createElement(
            "button",
            { onClick: () => onOpen(bundleUrlFor(run.run_id)) },
            `${world.title ?? world.world_id} — seed ${run.seed}`,
          ),
        );
      }),
    ),
  );
}
