/**
 * The book entry screen (su-app-06): the analyst's real opening book,
 * entered before the decade starts.
 *
 * Opens pre-filled with the server's derived default (`GET /book/default`)
 * for THIS world's own sleeve set — never blank, and never a hardcoded
 * sleeve list or a hardcoded plan length (`liquid_sleeves` and the served
 * plan's array length drive both). Editing is shape validation only: the
 * running total (`sum(liquid) + sum(rung nav_true) + cash`) is the one
 * piece of arithmetic this screen performs. Everything that scores — NAV,
 * coverage, alpha — comes from the server (DN-3 W5); this screen computes
 * none of it.
 *
 * Ranked eligibility is a SERVER-enforced rule; the note here only states
 * the current position (book+plan still exactly the served default) so the
 * player isn't surprised at `POST /sessions`.
 *
 * su-app-07 adds the institution's POLICY TARGETS beside those opening
 * VALUES, and an optional reporting BAND per sleeve. Three things about them
 * are load-bearing:
 *
 *  1. The targets are the SERVER's (Ruling D). `GET /book/default` returns a
 *     book whose `targets` already equal its values, and an untouched
 *     pre-fill posts them VERBATIM. Synthesizing them here — or posting
 *     `ranges: {}` where the server sent `null` — makes the posted document
 *     digest differently from the served default, and `POST /sessions`
 *     demotes a differing book to practice-only. That would strip RANKED
 *     from a book nobody edited, silently.
 *  2. Bands REPORT; they do not rebalance. Nothing the engine produces
 *     changes because one was declared.
 *  3. Band STATUS — ok / watch / breach — is never computed here. It arrives
 *     already judged on the session document's `band_report` (DN-3 W5). This
 *     screen validates SHAPE only: finite, non-negative, `lo < hi`, and the
 *     targets totalling 100 with cash.
 *
 * app-open-01 (owner-dictated 2026-08-16) makes three further changes, all
 * display/default only — the contract above is otherwise unchanged:
 *
 *  1. The served DEFAULT band is now +/-10% of the sleeve's own target
 *     (`default_band` in `ah/port/book.py`), not empty. This screen still
 *     never invents a band; it renders whatever `book.ranges` the server
 *     sent, same as before — an untouched pre-fill still posts the SAME
 *     document it was served, so ranked eligibility still survives it.
 *  2. The private sleeves (pe/pc/re, and infra since ER-14's close-out) are
 *     rows of the SAME targets/bands table as the liquid sleeves, not a
 *     separate strip above each ladder —
 *     same columns, same validation. A private row's `value` cell is
 *     read-only text (the ladder below it, summed at nav_true); it is
 *     edited on the ladder, not here.
 *  3. Every sleeve name rendered as visible text uses its full, capitalized
 *     label (`sleeveLabel`, `./lib/sleeveLabels`) — never the bare code.
 *     `aria-label`s keep the codes: they are accessibility/test hooks, not
 *     text the player reads, and the server contract's field names
 *     (`liquid`/`private`/`targets`/`ranges` keys) are untouched.
 *
 * app-open-02 (owner-dictated 2026-08-16): each private ladder's header adds
 * a "set a new value" alternative to hand-editing rungs one at a time. The
 * typed value is sent to `GET /book/ladder`, which runs the SAME
 * `_seed_ladder` builder the served default's rungs came from
 * (`ah/play.py`) — never a second, client-side ladder. A successful rebuild
 * replaces `book.private[sleeve]` WHOLESALE with the returned rungs, which
 * re-derives the value cell and every fault exactly as a hand-edited rung
 * does; a refused rebuild changes nothing (never partially applied) and
 * surfaces the server's own detail message next to that sleeve's ladder.
 * Rebuilding counts as an edit like any other — it changes the book's
 * digest, so ranked eligibility is lost exactly as a hand-edited rung would
 * lose it; this file does not touch that machinery.
 *
 * Task 8 (owner-dictated 2026-08-16), "so they can move on easily": the
 * screen was one long scroll; it becomes three TABS — Targets and bands /
 * Historical vintages / Cashflow projections — with a single "Play" control
 * at the top of the tab bar. Tabs are display-only (`role="tab"`/
 * `role="tabpanel"`, `hidden` on the inactive panels): all three stay
 * mounted, so typed input, the derived book and shape faults survive any tab
 * round-trip, and a fault raised on a hidden tab still blocks Play. Play
 * replaces the old bottom "Continue" button one-for-one — same gating (`!
 * ready`), same `onReady(book, plan, isDefault)` call, same navigation
 * consequence in the caller — there is no second, divergent commit control.
 * The fault list moves with it, next to Play, and is rendered in exactly one
 * place. This pass also drops the visible word "sleeve" from the screen
 * ("Asset class" column head, "Private asset classes'" note) — aria-labels
 * and the `liquid`/`private` contract keys are untouched, same judgment as
 * app-open-01 delta 3.
 *
 * app-open-03 (owner-reported defects, 2026-08-19) reworks two behaviours:
 *
 *  1. VALUES ARE THE SOURCE OF TRUTH; WEIGHTS DERIVE. The typed values are
 *     free-scale — a WEIGHT column (value/total, live) sits beside them and
 *     can never sum to anything but 100 by construction, so the old
 *     "the book does not total 100" gate is GONE (inverted test in
 *     BookEntry.test.tsx): any book with a positive total can Play. On Play
 *     the posted document is the book RESCALED to the contract's 100-point
 *     scale (`effectiveBook` — every money field linearly, which preserves
 *     the recycling identity; the typed targets rescaled to fill what the
 *     cash weight leaves, which is the same identity `validate_book`
 *     enforces). An UNTOUCHED book still posts VERBATIM — the rescale is
 *     bypassed entirely when the book deep-equals the served default, so
 *     Ruling D's digest property survives to the float.
 *     Weights are EDITABLE, symmetrically: typing a weight gives that class
 *     that share of the UNCHANGED total; the other liquid classes and cash
 *     absorb the difference proportionally (equally when they hold nothing).
 *     Private classes' weight is read-only here for the same reason their
 *     value is — it moves on the ladder, or via rebuild.
 *  2. THE COMMITMENT PLAN FOLLOWS THE BOOK. Every book edit (values,
 *     weights, targets, vintage rungs, a ladder rebuild) re-posts the
 *     current book to `POST /book/plan` (debounced) and replaces the plan
 *     grid wholesale with the SERVER's answer — `book_commitment_plan` in
 *     `ah/play.py`, the default window rule with DN-5's policy flex at the
 *     book's own opening reported private weight. No plan math is ever
 *     computed here (DN-3 W5); the pre-existing client-side mirror of
 *     `validate_plan`'s cap check is unchanged, now fed the POSTED targets.
 *     Hand-editing a plan cell takes the plan over (`planEdited`): it stops
 *     following book edits — stated in copy on the tab — and "Reset plan"
 *     hands it back to the server's derivation.
 */

import { Fragment, useEffect, useMemo, useState } from "react";
import { usd } from "./lib/money";
import {
  getDefaultBook,
  planForBook,
  rebuildLadder,
  SessionApiError,
  type Book,
  type DefaultBookResponse,
  type Plan,
  type PlanCap,
  type Rung,
  type UnfundedNote,
} from "./lib/session";
import { sleeveLabel } from "./lib/sleeveLabels";
import { VintageChart } from "./components/VintageChart";

const RUNG_FIELDS = [
  "vintage_year",
  "committed",
  "paid_in",
  "unfunded",
  "nav_true",
  "nav_reported",
  "cumulative_distributions",
] as const;
type RungField = (typeof RUNG_FIELDS)[number];

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

/** task 8: the three tabs, in the owner's order — default is the first. */
type TabId = "targets" | "vintages" | "cashflow";
const TABS: { id: TabId; label: string }[] = [
  { id: "targets", label: "Targets and bands" },
  { id: "vintages", label: "Historical vintages" },
  { id: "cashflow", label: "Cashflow projections" },
];

function rungField(rung: Rung, field: RungField): number {
  if (field === "vintage_year") return rung.identity.vintage_year;
  if (field === "committed" || field === "paid_in" || field === "unfunded") {
    return rung.commitment[field];
  }
  return rung.value[field];
}

function withRungField(rung: Rung, field: RungField, value: number): Rung {
  if (field === "vintage_year") {
    return { ...rung, identity: { ...rung.identity, vintage_year: value } };
  }
  if (field === "committed" || field === "paid_in" || field === "unfunded") {
    return { ...rung, commitment: { ...rung.commitment, [field]: value } };
  }
  return { ...rung, value: { ...rung.value, [field]: value } };
}

/** the one piece of arithmetic this screen does — everything else that
 * matters is server-computed. */
function bookTotal(book: Book): number {
  const liquidSum = Object.values(book.liquid).reduce((a, b) => a + b, 0);
  const privateSum = Object.values(book.private)
    .flat()
    .reduce((a, r) => a + r.value.nav_true, 0);
  return liquidSum + privateSum + book.cash;
}

/** every sleeve's HELD value: liquid points as entered, each private sleeve's
 * ladder summed at `nav_true`. The denominator side of the drift readout, and
 * the same fallback the server resolves a target-less book against
 * (`OpeningBook.effective_targets`) rather than a second rule invented here. */
function sleeveValues(book: Book): Record<string, number> {
  const priv = Object.fromEntries(
    Object.entries(book.private).map(([sleeve, rungs]) => [
      sleeve,
      rungs.reduce((a, r) => a + r.value.nav_true, 0),
    ]),
  );
  return { ...book.liquid, ...priv };
}

/** the targets to SHOW. An `opening-book-0.2` default always carries them, so
 * the fallback is reached only by a retained `0.1` book (su-app-06 I3). */
function shownTargets(book: Book): Record<string, number> {
  return book.targets ?? sleeveValues(book);
}

/** app-open-03: when a rescale would move a number by less than the server's
 * own BOOK_TOLERANCE (1e-6, `ah/port/book.py`), skip it entirely — an
 * already-consistent book posts the exact floats that were typed (or served),
 * never a `x * (100/total)` restatement of them that differs in the last ulp
 * and churns the digest. */
const SCALE_TOLERANCE = 1e-6;

/** one rung, every MONEY field scaled linearly. `identity` is untouched
 * (vintage_year and cohort_id are not money), and a linear scale preserves
 * the recycling identity `paid_in + unfunded = committed + recycled` exactly
 * to float dust — which is why this is legal client-side bookkeeping and not
 * value math: it invents no number the analyst didn't type, it restates all
 * of them on the contract's 100-point scale. */
function scaleSection<T extends Record<string, unknown>>(section: T, f: number): T {
  return Object.fromEntries(
    Object.entries(section).map(([k, v]) => [k, typeof v === "number" ? v * f : v]),
  ) as T;
}

function scaleRung(rung: Rung, f: number): Rung {
  return {
    ...rung,
    commitment: scaleSection(rung.commitment, f),
    value: scaleSection(rung.value, f),
  };
}

/** the POLICY targets as they will be POSTED: the typed targets are relative
 * numbers, rescaled so that `sum(targets) + cash weight = 100` — the exact
 * identity `validate_book` enforces, resolved here BY CONSTRUCTION instead of
 * bounced back at the analyst as a decimals-chasing fault (the app-open-03
 * deadlock: a value edit used to move the required target total out from
 * under targets that were entered correctly). Already-consistent targets are
 * returned as typed (see SCALE_TOLERANCE). */
function postedTargets(book: Book, total: number): Record<string, number> {
  const typed = shownTargets(book);
  if (!(total > 0)) return typed;
  const cashWeight = (book.cash / total) * 100;
  const sum = Object.values(typed).reduce((a, b) => a + b, 0);
  if (!(sum > 0) || Math.abs(sum + cashWeight - 100) <= SCALE_TOLERANCE) return typed;
  const g = (100 - cashWeight) / sum;
  return Object.fromEntries(Object.entries(typed).map(([s, t]) => [s, t * g]));
}

/** app-open-03 contract: the DOCUMENT Play posts — the typed book restated on
 * the contract's 100-point scale. Values, cash and every rung money field
 * scale by `100/total`; targets by `postedTargets`'s rule. Callers bypass
 * this entirely for an untouched book (deep-equal to the served default), so
 * the Ruling-D verbatim-post property is preserved exactly, not just within
 * tolerance. */
function effectiveBook(book: Book): Book {
  const total = bookTotal(book);
  if (!(total > 0)) return book; // gated by its own fault; never posted
  let out = book;
  if (Math.abs(total - 100) > SCALE_TOLERANCE) {
    const f = 100 / total;
    out = {
      ...out,
      liquid: Object.fromEntries(Object.entries(out.liquid).map(([s, v]) => [s, v * f])),
      cash: out.cash * f,
      private: Object.fromEntries(
        Object.entries(out.private).map(([s, rungs]) => [s, rungs.map((r) => scaleRung(r, f))]),
      ),
    };
  }
  if (out.targets) {
    const posted = postedTargets(book, total);
    if (posted !== out.targets) out = { ...out, targets: posted };
  }
  return out;
}

/** app-open-03 contract B, the one-sentence rule (also stated in the screen's
 * copy): typing a weight gives that class that share of the UNCHANGED total;
 * the other liquid classes and cash absorb the difference proportionally
 * (equally when they hold nothing), and private classes' values move only on
 * their ladders. Weights therefore keep summing to 100 by construction. The
 * typed weight is clamped to what the liquid side can actually cede —
 * private NAV cannot be taken from here — and when the clamp fires the
 * result SAYS so (`cappedAt`, the weight actually applied, in percent):
 * review fix round 1, a silent clamp is below contract C's wording bar. */
function applyWeightEdit(
  book: Book,
  sleeve: string,
  weightPct: number,
): { book: Book; cappedAt: number | null } {
  const total = bookTotal(book);
  if (!(total > 0) || !Number.isFinite(weightPct)) return { book, cappedAt: null };
  const isCash = sleeve === "cash";
  const current = isCash ? book.cash : book.liquid[sleeve];
  if (current === undefined) return { book, cappedAt: null };
  const privateSum = Object.values(book.private)
    .flat()
    .reduce((a, r) => a + r.value.nav_true, 0);
  // computed entries are rounded to 6dp — a typed "50" should produce 50,
  // not 50.000000000000006 of float dust from a many-term total. The dust
  // this leaves on the total is orders below SCALE_TOLERANCE's concern and
  // the posted book rescales anyway.
  const r6 = (v: number) => Math.round(v * 1e6) / 1e6;
  const liquidSide = total - privateSum; // this class + its absorbers
  const desired = (Math.min(Math.max(weightPct, 0), 100) / 100) * total;
  const capped = desired > liquidSide + 1e-9;
  const next = r6(Math.min(desired, liquidSide));
  const required = liquidSide - next; // what the absorbers must now hold
  const absorberSum = liquidSide - current;
  const others = Object.keys(book.liquid).filter((s) => s !== sleeve);
  const absorbers = isCash ? others : [...others, "cash"];
  const scaled = (v: number) =>
    r6(absorberSum > 0 ? v * (required / absorberSum) : required / absorbers.length);
  const liquid = Object.fromEntries(
    Object.entries(book.liquid).map(([s, v]) => [
      s,
      s === sleeve ? next : absorbers.includes(s) ? scaled(v) : v,
    ]),
  );
  const cash = isCash ? next : scaled(book.cash);
  return { book: { ...book, liquid, cash }, cappedAt: capped ? (next / total) * 100 : null };
}

/** a band mid-entry. Held as TEXT, not as numbers, because "" and 0 are
 * different answers here: an empty pair means "this sleeve declares no band"
 * while `0` is a legal floor, and `Number("")` is `0`. */
type RangeText = { lo: string; hi: string };
const EMPTY_RANGE: RangeText = { lo: "", hi: "" };

function rangeTextFrom(
  ranges: Record<string, [number, number]> | null | undefined,
): Record<string, RangeText> {
  if (!ranges) return {};
  return Object.fromEntries(
    Object.entries(ranges).map(([sleeve, [lo, hi]]) => [
      sleeve,
      { lo: String(lo), hi: String(hi) },
    ]),
  );
}

/** the entered bands in the contract's shape, or `null` when none is
 * complete. **Never `{}`** (Ruling D): the served default carries
 * `ranges: null`, and `{}` is a different document — the server would read it
 * as an edited book and demote the session to practice-only. */
function buildRanges(text: Record<string, RangeText>): Record<string, [number, number]> | null {
  const out: Record<string, [number, number]> = {};
  for (const [sleeve, pair] of Object.entries(text)) {
    if (pair.lo.trim() === "" || pair.hi.trim() === "") continue;
    const lo = Number(pair.lo);
    const hi = Number(pair.hi);
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) continue;
    out[sleeve] = [lo, hi];
  }
  return Object.keys(out).length > 0 ? out : null;
}

/** SHAPE faults on the bands: both sides or neither, numbers, and
 * `0 <= lo < hi <= 100` — the same rule `validate_book` enforces, so a band
 * this screen offers cannot be one the server then refuses. Band STATUS is
 * NOT computed here; ok/watch/breach is the server's `band_report`. */
function rangeFaults(text: Record<string, RangeText>): string[] {
  let half = false;
  let unparsed = false;
  let inverted = false;
  let outside = false;
  for (const pair of Object.values(text)) {
    const lo = pair.lo.trim();
    const hi = pair.hi.trim();
    if (lo === "" && hi === "") continue;
    if (lo === "" || hi === "") {
      half = true;
      continue;
    }
    const l = Number(lo);
    const h = Number(hi);
    if (!Number.isFinite(l) || !Number.isFinite(h)) {
      unparsed = true;
      continue;
    }
    if (l < 0 || h > 100) outside = true;
    if (l >= h) inverted = true;
  }
  const faults: string[] = [];
  if (half) faults.push("a band needs both lo and hi");
  if (unparsed) faults.push("a band is not a number");
  if (inverted) faults.push("a band needs lo below hi");
  if (outside) faults.push("a band must lie between 0 and 100");
  return faults;
}

/**
 * Branch-review I2: a client-side PRE-FLIGHT mirror of
 * `ah.port.book.validate_plan`'s per-window cap check, run against the
 * CURRENT typed targets and the CURRENT plan grid — not the served
 * defaults. `validate_plan` refuses a plan window whose points exceed
 * `COMMIT_CAP_MULTIPLE * target * annual_rate`; the default plan is built
 * from the WORLD's targets, so a player who lowers a private target enough
 * (without ever touching the Cashflow projections tab) can otherwise reach
 * `POST /sessions` and be refused there, naming a plan year they never
 * touched. This surfaces the same refusal here, in plain language, before
 * Play — the exact constants and the exact comparison strictness
 * (`points > cap`, not `>=`) mirror `validate_plan`, and `cap` is the
 * server's OWN served `plan_cap` (never a re-derived literal copy, which
 * could silently drift from `ah.play`'s constants).
 */
function planCapFaults(plan: Plan, targets: Record<string, number>, cap: PlanCap): string[] {
  const faults: string[] = [];
  for (const [sleeve, years] of Object.entries(plan.points)) {
    const target = targets[sleeve];
    if (!Number.isFinite(target)) continue; // a blank/NaN target is already reported elsewhere
    const capValue = cap.multiple * target * cap.annual_rate;
    years.forEach((points, k) => {
      if (!Number.isFinite(points) || points <= capValue) return;
      faults.push(
        `${sleeve} plan year ${k} (${points.toFixed(1)}) exceeds the commitment cap for a ` +
          `${target.toFixed(1)} target - lower that plan year on the Cashflow projections ` +
          "tab, or raise the target",
      );
    });
  }
  return faults;
}

function fmt1(x: number): string {
  return Number.isFinite(x) ? x.toFixed(1) : "—";
}

/** a signed points figure. The `< 0.05` fold keeps float dust off the screen
 * as "+0.0" rather than "-0.0". */
function signed(x: number): string {
  if (!Number.isFinite(x)) return "—";
  const v = Math.abs(x) < 0.05 ? 0 : x;
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}`;
}

/** every field that fails `test`, NAMED (app-open-03 contract C: a fault that
 * still blocks must say exactly what to change, in plain words) — the same
 * fields `allFieldsFinite`/`allFieldsNonNegative` used to scan anonymously.
 * A SHAPE check either way: it compares numbers the analyst typed and
 * computes no value, no NAV and no coverage (DN-3 W5 leaves those on the
 * server). Targets are EXCLUDED here — a negative target has its own,
 * separately-worded fault, and blank targets are named like any other. */
function failingFields(
  book: Book,
  plan: Plan,
  test: (n: number) => boolean,
  includeTargets: boolean,
): string[] {
  const out: string[] = [];
  for (const [s, v] of Object.entries(book.liquid)) if (test(v)) out.push(`${s} value`);
  if (includeTargets) {
    for (const [s, v] of Object.entries(book.targets ?? {})) if (test(v)) out.push(`${s} target`);
  }
  if (test(book.cash)) out.push("cash");
  for (const [s, rungs] of Object.entries(book.private)) {
    rungs.forEach((r, i) => {
      for (const f of RUNG_FIELDS) if (test(rungField(r, f))) out.push(`${s} rung ${i} ${f}`);
    });
  }
  for (const [s, years] of Object.entries(plan.points)) {
    years.forEach((v, k) => {
      if (test(v)) out.push(`${s} plan year ${k}`);
    });
  }
  return out;
}

/** the first few offenders, named; the rest counted. */
function nameFields(fields: string[]): string {
  const shown = fields.slice(0, 3).join(", ");
  return fields.length > 3 ? `${shown} and ${fields.length - 3} more` : shown;
}

/** `validate_book`'s ``RUNG_TOLERANCE`` — the SERVER's own tolerance, so a
 * book this screen offers cannot be one the server then refuses on the
 * identity, and one it blocks cannot be one the server would have taken. */
const RUNG_TOLERANCE = 1e-9;

/** spec section 7: `paid_in + unfunded = committed + cumulative_recycled`.
 * Deliberately NOT the simpler `paid_in + unfunded = committed`, which
 * recycling legitimately breaks — the same note `ah/port/book.py` carries.
 * Returns the offending rungs NAMED (sleeve, rung index, vintage) rather
 * than a boolean — review fix round 1 (app-open-03): every blocker on this
 * screen meets contract C's bar, saying exactly what is wrong and where to
 * change it. Empty means the identity holds everywhere. */
function recyclingBreaks(book: Book): string[] {
  const out: string[] = [];
  for (const [sleeve, rungs] of Object.entries(book.private)) {
    rungs.forEach((r, i) => {
      const lhs = r.commitment.paid_in + r.commitment.unfunded;
      const rhs = r.commitment.committed + r.commitment.cumulative_recycled;
      if (Math.abs(lhs - rhs) > RUNG_TOLERANCE) {
        out.push(`${sleeve} rung ${i} (vintage ${r.identity.vintage_year})`);
      }
    });
  }
  return out;
}

export function BookEntry({
  runId,
  initialBook,
  initialPlan,
  onReady,
  onCancel,
  planRecomputeDelayMs = 300,
}: {
  runId: string;
  /** su-app-06 (I3): what the analyst entered last time this screen was
   * open. `POST /sessions` happens two screens later, so a 422 there used to
   * throw away up to 210 typed fields — the screen re-seeded from the server
   * default on the way back in. Seeding from these instead makes a refusal
   * recoverable. Undefined on the first visit. The server's own default is
   * still fetched regardless: it is what `isDefault` and the per-sleeve
   * resets compare against, and it must stay the server's number. */
  initialBook?: Book;
  initialPlan?: Plan;
  onReady: (book: Book, plan: Plan, isDefault: boolean) => void;
  onCancel: () => void;
  /** app-open-03: how long a book edit settles before the plan recompute
   * round-trip fires. Tests pass 0 so a single macrotask flush lands it;
   * the default keeps a fast typist from posting the book per keystroke. */
  planRecomputeDelayMs?: number;
}) {
  const [resp, setResp] = useState<DefaultBookResponse | null>(null);
  const [book, setBook] = useState<Book | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  /** the band inputs, as typed. `book.ranges` is derived from this on every
   * edit — it is the posted document, this is the editing surface. */
  const [rangeText, setRangeText] = useState<Record<string, RangeText>>({});
  const [error, setError] = useState<string | null>(null);
  /** app-open-02: the "rebuild to this value" input, per private sleeve, as
   * TYPED text (not a number) — same reasoning as `rangeText`: an
   * in-progress edit is not yet a value. */
  const [rebuildText, setRebuildText] = useState<Record<string, string>>({});
  /** app-open-02: the last rebuild's refusal, per sleeve — this screen's own
   * fault surface for the endpoint, styled and worded exactly like
   * `shapeFaults` (`className="book-note error"`) rather than the
   * full-screen `error` above, which is reserved for "the entry screen
   * itself could not load" and would otherwise discard every other typed
   * field on a single ladder's refusal. */
  const [ladderError, setLadderError] = useState<Record<string, string | null>>({});
  const [rebuilding, setRebuilding] = useState<string | null>(null);
  /** task 8: display-only — which panel is showing. All three stay mounted
   * regardless (see the file header), so this never gates what state exists,
   * only what is visible. */
  const [activeTab, setActiveTab] = useState<TabId>("targets");
  /** app-open-03: an in-progress weight edit, as TYPED — same reasoning as
   * `rangeText`/`rebuildText`. Keyed to one input at a time (the focused
   * one); every unfocused weight cell shows the DERIVED share. */
  const [weightDraft, setWeightDraft] = useState<{ sleeve: string; text: string } | null>(null);
  /** review fix round 1 (app-open-03): the last weight edit that was CAPPED
   * (typed more than liquid+cash can supply), with the weight actually
   * applied — rendered as one plain sentence under the affected row.
   * Cleared by the next un-capped weight edit. */
  const [weightCap, setWeightCap] = useState<{ sleeve: string; applied: number } | null>(null);
  /** app-open-03: true once the analyst hand-edits a plan cell — the plan is
   * theirs from then on and stops following book edits (stated in copy on
   * the Cashflow tab); "Reset plan" hands it back to the server's
   * derivation. Also set on reopening with a retained plan that differs
   * from the served default: this screen cannot tell a hand-edited retained
   * plan from an auto-derived one, and clobbering typed cells is the worse
   * failure. */
  const [planEdited, setPlanEdited] = useState(false);
  /** app-open-03: the plan recompute round-trip's state. `error` renders on
   * the Cashflow tab (the server's own message); it does not gate Play —
   * the cap pre-flight and `POST /sessions` still guard the contract. */
  const [planSync, setPlanSync] = useState<{ status: "idle" | "pending" | "error"; message?: string }>(
    { status: "idle" },
  );
  /** app-open-04 Item C: the server's unfunded-pause note for the CURRENT
   * derived plan (`POST /book/plan`'s `unfunded` block). Null for the
   * untouched default (its ladders sit at the steady state by construction,
   * so the server always reports inactive there) and after a failed
   * recompute. Rendered only while the plan still FOLLOWS the book — a
   * hand-edited plan is the analyst's own and the sentence would describe a
   * derivation no longer on screen. */
  const [planUnfunded, setPlanUnfunded] = useState<UnfundedNote | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDefaultBook(runId)
      .then((r) => {
        if (cancelled) return;
        const seeded = deepClone(initialBook ?? r.book);
        setResp(r);
        setBook(seeded);
        setPlan(deepClone(initialPlan ?? r.plan));
        setPlanEdited(
          initialPlan !== undefined && JSON.stringify(initialPlan) !== JSON.stringify(r.plan),
        );
        // I3 again: bands typed before a refused POST come back with the book
        setRangeText(rangeTextFrom(seeded.ranges));
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [runId, initialBook, initialPlan]);

  const isDefault = useMemo(() => {
    if (!resp || !book || !plan) return true;
    return (
      JSON.stringify(book) === JSON.stringify(resp.book) &&
      JSON.stringify(plan) === JSON.stringify(resp.plan)
    );
  }, [resp, book, plan]);

  const total = book ? bookTotal(book) : NaN;
  const totalRounded = Number.isFinite(total) ? Math.round(total * 100) / 100 : NaN;
  // app-open-03: values are the source of truth and WEIGHTS DERIVE — each
  // class's share of the typed total, live, summing to 100 by construction.
  // The policy side derives the same way now: the typed targets are relative
  // numbers, and the policy weight shown is the target as it will be POSTED
  // (`postedTargets` — filling exactly what the cash weight leaves), so the
  // readout and the posted document cannot disagree.
  const targets = book ? shownTargets(book) : {};
  const values = book ? sleeveValues(book) : {};
  const targetSum = Object.values(targets).reduce((a, b) => a + b, 0);
  const posted = book ? postedTargets(book, total) : {};
  const cashWeight = book ? (book.cash / total) * 100 : NaN;
  const policyWeight = (sleeve: string) => posted[sleeve] ?? NaN;
  const heldWeight = (sleeve: string) => ((values[sleeve] ?? NaN) / total) * 100;
  const drift = (sleeve: string) => heldWeight(sleeve) - policyWeight(sleeve);
  // Each refusal the SERVER can raise on shape gets its own named check, so
  // the panel can say which one is blocking rather than only that something
  // is (spec section 6's validity panel) — and since app-open-03 (contract
  // C) each fault NAMES the offending field, because a message that cannot
  // be acted on is a deadlock with extra words.
  // A blank field makes every OTHER rule false as well (NaN fails each
  // comparison), so it is reported alone rather than alongside three
  // consequences of itself.
  const shapeFaults: string[] = [];
  if (book && plan) {
    const blank = failingFields(book, plan, (n) => !Number.isFinite(n), true);
    if (blank.length > 0) {
      shapeFaults.push(`blank or not a number: ${nameFields(blank)}`);
    } else {
      const negative = failingFields(book, plan, (n) => n < 0, false);
      if (negative.length > 0) {
        shapeFaults.push(`negative: ${nameFields(negative)} - every entry must be zero or more`);
      }
      const broken = recyclingBreaks(book);
      if (broken.length > 0) {
        shapeFaults.push(
          `paid_in + unfunded must equal committed + recycled, and fails on ${nameFields(broken)}` +
            " - adjust one of those four fields on the Historical vintages tab",
        );
      }
      // app-open-03: the old "the book does not total 100" gate is GONE —
      // the posted book is the typed one rescaled to 100 (`effectiveBook`),
      // so the only total that can still block is one nothing could scale.
      if (!(total > 0)) {
        shapeFaults.push("the book needs a positive total - raise a value on some class or cash");
      } else if (book.targets) {
        // negative targets keep their own, separately-worded fault; the old
        // "targets do not total 100" gate is gone the same way (typed
        // targets are relative and rescale to fill what cash leaves).
        const negativeTargets = Object.entries(targets)
          .filter(([, t]) => t < 0)
          .map(([s]) => `${s}`);
        if (negativeTargets.length > 0) {
          shapeFaults.push(`a target is negative: ${nameFields(negativeTargets)}`);
        } else if (!(targetSum > 0) && cashWeight < 100 - SCALE_TOLERANCE) {
          shapeFaults.push(
            "enter at least one positive target - the policy weights fill what cash leaves",
          );
        }
      }
      shapeFaults.push(...rangeFaults(rangeText));
      // I2: only meaningful once the server has told us its cap constants
      // (`resp.plan_cap`, always present once the default has loaded).
      // Fed the POSTED targets since app-open-03 — the exact numbers
      // `validate_plan` will see at the door.
      if (resp?.plan_cap && total > 0) {
        shapeFaults.push(...planCapFaults(plan, posted, resp.plan_cap));
      }
    }
  }
  const ready = !!book && !!plan && shapeFaults.length === 0;

  // app-open-03: THE COMMITMENT PLAN FOLLOWS THE BOOK. Any change to the
  // book (values, weights, targets, rungs, a rebuilt ladder) re-posts the
  // CURRENT book — as it would be posted, `effectiveBook` — to
  // `POST /book/plan`, debounced, and replaces the plan grid with the
  // server's answer. The derivation lives server-side (DN-3 W5); this
  // effect moves documents, never numbers. Skipped while the plan is
  // hand-edited (`planEdited`), while the book is exactly the served
  // default (the served plan IS its answer, restored verbatim so the
  // untouched digest survives), and while the book has blocking faults of
  // its own (a book `validate_book` would refuse has no plan to ask for).
  const bookJson = book ? JSON.stringify(book) : null;
  const defaultBookJson = useMemo(() => (resp ? JSON.stringify(resp.book) : null), [resp]);
  const bookBlocked =
    !book ||
    !plan ||
    !(total > 0) ||
    failingFields(book, plan, (n) => !Number.isFinite(n), true).length > 0 ||
    failingFields(book, plan, (n) => n < 0, false).length > 0 ||
    Object.values(targets).some((t) => t < 0) ||
    (!(targetSum > 0) && cashWeight < 100 - SCALE_TOLERANCE) ||
    recyclingBreaks(book).length > 0;
  useEffect(() => {
    if (!resp || !book || !bookJson) return;
    if (planEdited) return;
    if (bookJson === defaultBookJson) {
      setPlan((p) =>
        JSON.stringify(p) === JSON.stringify(resp.plan) ? p : deepClone(resp.plan),
      );
      setPlanSync((s) => (s.status === "idle" ? s : { status: "idle" }));
      setPlanUnfunded(null);
      return;
    }
    if (bookBlocked) return;
    let cancelled = false;
    setPlanSync({ status: "pending" });
    const timer = setTimeout(() => {
      planForBook(runId, effectiveBook(book))
        .then(({ plan: derived, unfunded }) => {
          if (cancelled) return;
          setPlan(derived);
          setPlanSync({ status: "idle" });
          // app-open-04 Item C: the note rides with the plan it describes;
          // absent on an older server, which renders as "no pause".
          setPlanUnfunded(unfunded ?? null);
        })
        .catch((e) => {
          if (cancelled) return;
          setPlanSync({
            status: "error",
            message: e instanceof SessionApiError ? e.message : String(e),
          });
          setPlanUnfunded(null);
        });
    }, planRecomputeDelayMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bookJson is the
    // book's identity for this effect; book itself is read from the closure.
  }, [bookJson, defaultBookJson, planEdited, resp, runId, bookBlocked, planRecomputeDelayMs]);

  if (error) {
    return (
      <main className="shell book-entry">
        <p className="error">{error}</p>
        <button onClick={onCancel}>back</button>
      </main>
    );
  }

  if (!resp || !book || !plan) {
    return (
      <main className="shell book-entry">
        <p>Loading the book…</p>
      </main>
    );
  }

  const privateSleeves = Object.keys(resp.book.private);

  const setLiquid = (sleeve: string, value: number) =>
    setBook((b) => (b ? { ...b, liquid: { ...b.liquid, [sleeve]: value } } : b));

  const setCash = (value: number) => setBook((b) => (b ? { ...b, cash: value } : b));

  /** a target edit writes the WHOLE map back, because `targets` is all-or-
   * nothing on the contract: it names every sleeve or it is absent. */
  const setTarget = (sleeve: string, value: number) =>
    setBook((b) => (b ? { ...b, targets: { ...shownTargets(b), [sleeve]: value } } : b));

  /** a band edit updates the text and re-derives `book.ranges` from ALL of it.
   * Re-derived rather than patched so that clearing the last band puts the key
   * back to `null` — the exact document the server served — instead of leaving
   * an empty object behind and costing the session its ranked eligibility. */
  const setRange = (sleeve: string, edge: "lo" | "hi", text: string) => {
    const next = {
      ...rangeText,
      [sleeve]: { ...(rangeText[sleeve] ?? EMPTY_RANGE), [edge]: text },
    };
    setRangeText(next);
    setBook((b) => (b ? { ...b, ranges: buildRanges(next) } : b));
  };

  /** app-open-03: one EDITABLE weight cell (liquid classes and cash). Shows
   * the derived share (1dp) except while being typed in; every keystroke
   * applies `applyWeightEdit`'s rule, so the weights row keeps summing to
   * 100 by construction. */
  const weightCell = (sleeve: string) => {
    const w = sleeve === "cash" ? cashWeight : heldWeight(sleeve);
    // the typed text stands in for the derived share only while it still
    // AGREES with it (within display rounding) — an edit anywhere else that
    // moves this class's weight retires the draft, so the cell can never
    // show a number the book no longer holds.
    const draft = weightDraft?.sleeve === sleeve ? weightDraft.text : null;
    const draftActive =
      draft !== null && Number.isFinite(Number(draft)) && Math.abs(Number(draft) - w) < 0.05;
    const shown = draftActive
      ? draft
      : Number.isFinite(w)
        ? String(Math.round(w * 10) / 10)
        : "";
    return (
      <input
        type="number"
        className="policy-weight"
        aria-label={`${sleeve} weight`}
        value={shown}
        onFocus={() => setWeightDraft({ sleeve, text: shown })}
        onChange={(e) => {
          setWeightDraft({ sleeve, text: e.target.value });
          const n = Number(e.target.value);
          if (e.target.value.trim() !== "" && Number.isFinite(n)) {
            // review fix round 1: the clamp must not fire silently — when
            // the typed weight asks for more than liquid+cash can supply,
            // record the applied number so the row can say so.
            const applied = applyWeightEdit(book, sleeve, n);
            setBook(applied.book);
            setWeightCap(
              applied.cappedAt !== null ? { sleeve, applied: applied.cappedAt } : null,
            );
          }
        }}
        onBlur={() => setWeightDraft(null)}
      />
    );
  };

  /** review fix round 1: the capped-weight sentence, rendered directly under
   * the affected row (full grid width). The remainder figure is exact: when
   * the clamp fires the absorbers hold 0, so everything past the applied
   * weight IS the private side. */
  const weightCapNote = (sleeve: string) =>
    weightCap?.sleeve === sleeve ? (
      <p className="policy-cap-note" data-testid={`weight-cap-${sleeve}`}>
        {`${sleeveLabel(sleeve)}'s weight was capped at ${fmt1(weightCap.applied)}% - the other ` +
          `${fmt1(100 - weightCap.applied)}% of the book is private values, which only move on ` +
          "their ladders (edit rungs or rebuild on the Historical vintages tab)."}
      </p>
    ) : null;

  /** the band inputs for one sleeve, wherever the sleeve's row lives. */
  const bandInputs = (sleeve: string) => (
    <>
      <input
        type="number"
        className="policy-band"
        placeholder="—"
        aria-label={`${sleeve} range lo`}
        value={rangeText[sleeve]?.lo ?? ""}
        onChange={(e) => setRange(sleeve, "lo", e.target.value)}
      />
      <input
        type="number"
        className="policy-band"
        placeholder="—"
        aria-label={`${sleeve} range hi`}
        value={rangeText[sleeve]?.hi ?? ""}
        onChange={(e) => setRange(sleeve, "hi", e.target.value)}
      />
    </>
  );

  const setRung = (sleeve: string, i: number, field: RungField, value: number) =>
    setBook((b) => {
      if (!b) return b;
      const rungs = b.private[sleeve].map((r, idx) =>
        idx === i ? withRungField(r, field, value) : r,
      );
      return { ...b, private: { ...b.private, [sleeve]: rungs } };
    });

  const resetSleeve = (sleeve: string) =>
    setBook((b) =>
      b
        ? { ...b, private: { ...b.private, [sleeve]: deepClone(resp.book.private[sleeve]) } }
        : b,
    );

  /** app-open-02: the parsed, positive rebuild value for `sleeve`, or `null`
   * while the box is blank/unparseable — a SHAPE check only, same tier as
   * `allFieldsFinite`. Whether a POSITIVE-but-server-refused value (the
   * server also enforces `value > 0`) goes through is left to the server:
   * this screen does not duplicate that rule, only gates on "is this a
   * number at all" so the button is not clickable while empty. */
  const rebuildTargetValue = (sleeve: string): number | null => {
    const typed = rebuildText[sleeve]?.trim();
    if (!typed) return null;
    const n = Number(typed);
    return Number.isFinite(n) ? n : null;
  };

  const doRebuildLadder = (sleeve: string) => {
    const value = rebuildTargetValue(sleeve);
    if (value === null) return;
    setRebuilding(sleeve);
    setLadderError((e) => ({ ...e, [sleeve]: null }));
    rebuildLadder(runId, sleeve, value)
      .then(({ rungs }) => {
        // never partially applied: the sleeve's rungs are replaced WHOLESALE,
        // in one state update, or not at all.
        setBook((b) => (b ? { ...b, private: { ...b.private, [sleeve]: rungs } } : b));
      })
      .catch((e) => {
        setLadderError((prev) => ({
          ...prev,
          [sleeve]: e instanceof SessionApiError ? e.message : String(e),
        }));
      })
      .finally(() => setRebuilding(null));
  };

  const setPlanPoint = (sleeve: string, i: number, value: number) => {
    // app-open-03: a hand-edited cell takes the plan over — it stops
    // following book edits until "Reset plan" hands it back (stated in the
    // tab's copy, worded next to the control that changes it).
    setPlanEdited(true);
    setPlan((p) => {
      if (!p) return p;
      const points = p.points[sleeve].map((v, idx) => (idx === i ? value : v));
      return { ...p, points: { ...p.points, [sleeve]: points } };
    });
  };

  /** app-open-03: back to the SERVER's plan for the CURRENT book — the
   * served default immediately (also the correct answer for an untouched
   * book), then the recompute effect re-derives for an edited one now that
   * `planEdited` no longer holds it back. */
  const resetPlan = () => {
    setPlanEdited(false);
    setPlan(deepClone(resp.plan));
  };

  const planYears = plan.points[privateSleeves[0]] ?? [];

  return (
    <main className="shell book-entry">
      <h1>Enter the opening book</h1>
      <p className="tagline">
        Pre-filled with today&apos;s derived book. Edit only what your institution
        actually holds — everything else stays on the plan.
      </p>

      <div className="book-topbar">
        <div className="book-tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`book-tab-${t.id}`}
              aria-controls={`book-panel-${t.id}`}
              aria-selected={activeTab === t.id}
              className={`book-tab${activeTab === t.id ? " active" : ""}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="book-topbar-actions">
          {shapeFaults.length > 0 && (
            <p className="book-note error" data-testid="shape-faults">
              {shapeFaults.join("; ")}
            </p>
          )}
          <button
            type="button"
            className="book-play"
            disabled={!ready}
            // app-open-03: an edited book is posted AS IT WILL BE PLAYED —
            // rescaled to the contract's 100-point scale. An untouched book
            // still posts the served document verbatim (Ruling D).
            onClick={() =>
              onReady(bookJson === defaultBookJson ? book : effectiveBook(book), plan, isDefault)
            }
          >
            Play
          </button>
        </div>
      </div>

      <div
        role="tabpanel"
        id="book-panel-targets"
        aria-labelledby="book-tab-targets"
        hidden={activeTab !== "targets"}
      >
      <section className="setup book-liquid">
        <h2>Targets and bands</h2>
        <p className="book-note">
          <strong>Value</strong> is what you hold today, in any units — its{" "}
          <strong>weight</strong> beside it is that class's share of the total,
          kept in step live, and the book is entered as those weights (totalling
          100) when you press Play. Type either one: typing a weight keeps the
          total fixed and scales the other liquid classes and cash to absorb the
          difference. <strong>Target</strong> is your policy allocation — relative
          numbers that fill whatever share cash leaves — and it is what the
          commitment programme paces against. The <strong>band</strong> is
          optional and <strong>reports only</strong> — nothing rebalances to it.
          Private asset classes' value is the ladder below it, summed — edit it
          there (or rebuild it to a new value), not here.
        </p>
        <div className="policy-grid">
          <div className="policy-head">
            <span>Asset class</span>
            <span>value</span>
            <span>weight</span>
            <span>target</span>
            <span>policy wt</span>
            <span>drift</span>
            <span>band lo</span>
            <span>band hi</span>
          </div>
          {[...resp.liquid_sleeves, ...privateSleeves].map((sleeve) => {
            const isPrivate = privateSleeves.includes(sleeve);
            return (
              <Fragment key={sleeve}>
              <div className="policy-row">
                <span className="policy-name">{sleeveLabel(sleeve)}</span>
                {isPrivate ? (
                  <span className="policy-value" data-testid={`value-${sleeve}`}>
                    {fmt1(values[sleeve])}
                  </span>
                ) : (
                  <input
                    type="number"
                    aria-label={sleeve}
                    value={Number.isFinite(book.liquid[sleeve]) ? book.liquid[sleeve] : ""}
                    onChange={(e) => setLiquid(sleeve, Number(e.target.value))}
                  />
                )}
                {isPrivate ? (
                  // read-only for the same reason the value cell is: a
                  // private class's exposure moves on its LADDER (or via
                  // rebuild), never by scaling history from this row.
                  <span className="policy-wt" data-testid={`weight-${sleeve}`}>
                    {fmt1(heldWeight(sleeve))}%
                  </span>
                ) : (
                  weightCell(sleeve)
                )}
                <input
                  type="number"
                  aria-label={`${sleeve} target`}
                  value={Number.isFinite(targets[sleeve]) ? targets[sleeve] : ""}
                  onChange={(e) => setTarget(sleeve, Number(e.target.value))}
                />
                <span className="policy-wt" data-testid={`target-weight-${sleeve}`}>
                  {fmt1(policyWeight(sleeve))}%
                </span>
                <span
                  className={`policy-drift${Math.abs(drift(sleeve)) < 0.05 ? " flat" : ""}`}
                  data-testid={`target-drift-${sleeve}`}
                >
                  {signed(drift(sleeve))}
                </span>
                {bandInputs(sleeve)}
              </div>
              {!isPrivate && weightCapNote(sleeve)}
              </Fragment>
            );
          })}
          <div className="policy-row">
            <span className="policy-name">{sleeveLabel("cash")}</span>
            <input
              type="number"
              aria-label="cash"
              value={Number.isFinite(book.cash) ? book.cash : ""}
              onChange={(e) => setCash(Number(e.target.value))}
            />
            {weightCell("cash")}
            <span className="policy-residual">
              cash is the residual — it carries no target and no band
            </span>
          </div>
          {weightCapNote("cash")}
        </div>
      </section>
      </div>

      <div
        role="tabpanel"
        id="book-panel-vintages"
        aria-labelledby="book-tab-vintages"
        hidden={activeTab !== "vintages"}
      >
      {privateSleeves.map((sleeve) => (
        <section key={sleeve} className="book-ladder">
          <div className="book-ladder-head">
            <h2>{sleeveLabel(sleeve)}</h2>
            <div className="book-ladder-actions">
              <input
                type="number"
                className="ladder-rebuild-value"
                aria-label={`${sleeve} rebuild value`}
                placeholder="new value"
                value={rebuildText[sleeve] ?? ""}
                onChange={(e) =>
                  setRebuildText((t) => ({ ...t, [sleeve]: e.target.value }))
                }
              />
              <button
                type="button"
                aria-label={`${sleeve} rebuild ladder`}
                disabled={rebuildTargetValue(sleeve) === null || rebuilding === sleeve}
                onClick={() => doRebuildLadder(sleeve)}
              >
                Rebuild ladder
              </button>
              <button type="button" onClick={() => resetSleeve(sleeve)}>
                {`Reset ${sleeveLabel(sleeve)}`}
              </button>
            </div>
          </div>
          {ladderError[sleeve] && (
            <p className="book-note error" data-testid={`ladder-error-${sleeve}`}>
              {ladderError[sleeve]}
            </p>
          )}
          {/* task 10 (owner-dictated 2026-08-16): the rung array passed here
              IS the live typed state, book.private[sleeve] — not a copy, not
              memoized — so editing a rung input below moves this chart on
              the very next render. */}
          <VintageChart rungs={book.private[sleeve]} />
          <div className="book-ladder-scroll">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  {RUNG_FIELDS.map((f) => (
                    <th key={f}>{f}</th>
                  ))}
                  <th>recallable</th>
                  <th>recycled</th>
                </tr>
              </thead>
              <tbody>
                {book.private[sleeve].map((rung, i) => (
                  <tr key={i} data-testid={`rung-${sleeve}`}>
                    <td>{i}</td>
                    {RUNG_FIELDS.map((field) => {
                      const v = rungField(rung, field);
                      return (
                        <td key={field}>
                          <input
                            type="number"
                            aria-label={`${sleeve} rung ${i} ${field}`}
                            value={Number.isFinite(v) ? v : ""}
                            onChange={(e) => setRung(sleeve, i, field, Number(e.target.value))}
                          />
                        </td>
                      );
                    })}
                    <td className="book-carry">{rung.commitment.recallable_balance}</td>
                    <td className="book-carry">{rung.commitment.cumulative_recycled}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      </div>

      <div
        role="tabpanel"
        id="book-panel-cashflow"
        aria-labelledby="book-tab-cashflow"
        hidden={activeTab !== "cashflow"}
      >
      <section className="book-plan">
        <div className="book-ladder-head">
          <h2>Commitment plan</h2>
          <button type="button" onClick={resetPlan}>
            Reset plan
          </button>
        </div>
        {/* app-open-03: the tab states its own rule in one sentence, next to
            the control that changes it (contract C's wording standard). */}
        <p className="book-note" data-testid="plan-note">
          {planEdited
            ? "You have taken this plan over by hand - it no longer follows your book " +
              "edits. Reset plan hands it back to the derived schedule."
            : "Derived by the server from your current book - targets, values and " +
              "vintage ladders - and recomputed whenever you change them. Edit any " +
              "cell to take the plan over by hand."}
        </p>
        {planSync.status === "error" && (
          <p className="book-note error" data-testid="plan-error">
            the commitment plan could not be recomputed: {planSync.message}
          </p>
        )}
        {/* app-open-04 Item C: one plain sentence when the server's derived
            plan is pausing commitments for this book — the numbers are the
            SERVED totals, rendered verbatim (DN-3 W5), and the sentence
            hides once the plan is hand-edited (it describes the derivation,
            which a taken-over plan no longer follows). */}
        {!planEdited && planUnfunded?.active && (
          <p className="book-note" data-testid="unfunded-pause-note">
            {`commitments pause while existing unfunded works off - your unfunded is ` +
              `${fmt1(planUnfunded.unfunded_total)} vs ${fmt1(planUnfunded.steady_state_total)} ` +
              "typical for this target"}
          </p>
        )}
        <div className="book-ladder-scroll">
          <table>
            <thead>
              <tr>
                <th>year</th>
                {privateSleeves.map((s) => (
                  <th key={s}>{sleeveLabel(s)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {planYears.map((_, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  {privateSleeves.map((s) => {
                    const v = plan.points[s]?.[i];
                    return (
                      <td key={s}>
                        <input
                          type="number"
                          aria-label={`${s} plan year ${i}`}
                          value={v !== undefined && Number.isFinite(v) ? v : ""}
                          onChange={(e) => setPlanPoint(s, i, Number(e.target.value))}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      </div>

      {/* app-open-01 item 1 (owner ruling 2026-08-16): every field on this
          screen is entered in points (the book totals 100), so the running
          totals stay points-first — the dollar figure rides ALONGSIDE via
          usd(), not in place of it, the same "keep the scored number, add
          the visceral one" treatment item 1 specifies for an index/alpha.
          Replacing the points figure outright here would strip the analyst
          of the one number every input on the screen can be checked
          against. */}
      <div className="book-rail">
        <div>
          <span className="k">Total</span>
          <span className="v" data-testid="book-total">
            {Number.isFinite(totalRounded) ? totalRounded : "—"}
            {Number.isFinite(totalRounded) && (
              <span className="book-rail-usd"> &middot; {usd(totalRounded)}</span>
            )}
          </span>
        </div>
        {/* app-open-03: the old "Targets + cash" running total is gone with
            its gate — targets are relative now and always fill 100 with cash
            by construction. The cash weight is the number that replaced it:
            the residual the policy weights are filling around. */}
        <div>
          <span className="k">Cash weight</span>
          <span className="v" data-testid="cash-weight">
            {Number.isFinite(cashWeight) ? `${fmt1(cashWeight)}%` : "—"}
          </span>
        </div>
      </div>

      {/* app-open-02 park (owner ruling 2026-08-16): ranked is parked, so
          this no longer states ranked ELIGIBILITY (that would be
          misleading while nothing offers ranked at all). It stays a
          neutral statement of the book's touched/untouched state — the
          `isDefault` distinction and its telemetry are unchanged, only the
          copy is. */}
      <p className="book-note" data-testid="ranked-note">
        {isDefault
          ? "This is the served default book. (Ranked play is parked; every session runs as practice.)"
          : "This book has been edited from the served default. (Ranked play is parked; every session runs as practice.)"}
      </p>

      <button onClick={onCancel}>back</button>
    </main>
  );
}
