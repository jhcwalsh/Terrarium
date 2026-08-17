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

/** The latest `created_at` among a world's runs. Doesn't assume the caller's
 * `runs` array is sorted (the server's is; a hand-built payload need not
 * be) — takes the max explicitly. */
function newestCreatedAt(world: WorldEntry): string {
  let max = "";
  for (const run of world.runs) if (run.created_at > max) max = run.created_at;
  return max;
}

/** The single newest run for a world, by `created_at`. */
function newestRun(world: WorldEntry): WorldRun | null {
  let best: WorldRun | null = null;
  for (const run of world.runs) {
    if (best === null || run.created_at > best.created_at) best = run;
  }
  return best;
}

/** The worlds this picker renders: `SHOWN_GENERATOR_IDS` only, collapsed to
 * one entry per `world_id` (the reported symptom — "The Lost Decade"
 * appearing twice — is two runs for the same world; keep the entry whose
 * newest run is the most recent). Worlds with no runs are dropped, since
 * there is nothing for their button to open. */
export function selectShownWorlds(worlds: WorldEntry[]): WorldEntry[] {
  const byWorldId = new Map<string, WorldEntry>();
  for (const world of worlds) {
    if (!world.generator_id || !SHOWN_GENERATOR_IDS.includes(world.generator_id)) continue;
    if (world.runs.length === 0) continue;
    const existing = byWorldId.get(world.world_id);
    if (!existing || newestCreatedAt(world) > newestCreatedAt(existing)) {
      byWorldId.set(world.world_id, world);
    }
  }
  return Array.from(byWorldId.values());
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
 * (`selectShownWorlds` — declared-stress only, deduped by `world_id`),
 * wired to that world's newest run. Renders nothing when there is no doc or
 * nothing survives the filter — `fetchWorlds` failed, hasn't resolved yet,
 * the store has no worlds, or none of them are declared-stress — so the
 * landing view falls back to exactly the picker/URL flow that already
 * existed. */
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
