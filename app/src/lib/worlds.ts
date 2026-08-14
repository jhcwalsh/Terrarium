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

/** The "Choose your decade" list: each world's runs as load buttons.
 * Renders nothing when there is no doc — `fetchWorlds` failed, hasn't
 * resolved yet, or the store has no worlds — so the landing view falls back
 * to exactly the picker/URL flow that already existed. */
export function WorldPicker({
  doc,
  onOpen,
}: {
  doc: WorldsDoc | null;
  onOpen: (url: string) => void;
}): ReactElement | null {
  if (!doc || doc.worlds.length === 0) return null;
  return createElement(
    "section",
    { className: "world-picker" },
    createElement("h2", null, "Choose your decade"),
    ...doc.worlds.map((world) =>
      createElement(
        "ul",
        { key: world.world_id },
        ...world.runs.map((run) =>
          createElement(
            "li",
            { key: run.run_id },
            createElement(
              "button",
              { onClick: () => onOpen(bundleUrlFor(run.run_id)) },
              `${world.title ?? world.world_id} — seed ${run.seed}`,
            ),
          ),
        ),
      ),
    ),
  );
}
