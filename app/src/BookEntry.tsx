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
 */

import { useEffect, useMemo, useState } from "react";
import {
  getDefaultBook,
  type Book,
  type DefaultBookResponse,
  type Plan,
  type Rung,
} from "./lib/session";

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

/** every editable field parses to a finite number — the shape check the
 * continue button gates on, independent of what the total happens to be. */
function allFieldsFinite(book: Book, plan: Plan): boolean {
  const liquidOk = Object.values(book.liquid).every(Number.isFinite);
  const targetsOk = Object.values(book.targets ?? {}).every(Number.isFinite);
  const cashOk = Number.isFinite(book.cash);
  const rungsOk = Object.values(book.private)
    .flat()
    .every((r) => RUNG_FIELDS.every((f) => Number.isFinite(rungField(r, f))));
  const planOk = Object.values(plan.points).every((arr) => arr.every(Number.isFinite));
  return liquidOk && targetsOk && cashOk && rungsOk && planOk;
}

/** spec section 7's first refusal: "negative anything". A SHAPE check — it
 * compares numbers the analyst typed against zero and computes no value, no
 * NAV and no coverage (DN-3 W5 leaves all of those on the server). */
function allFieldsNonNegative(book: Book, plan: Plan): boolean {
  const ok = (n: number) => n >= 0;
  return (
    Object.values(book.liquid).every(ok) &&
    ok(book.cash) &&
    Object.values(book.private)
      .flat()
      .every((r) => RUNG_FIELDS.every((f) => ok(rungField(r, f)))) &&
    Object.values(plan.points).every((arr) => arr.every(ok))
  );
}

/** `validate_book`'s ``RUNG_TOLERANCE`` — the SERVER's own tolerance, so a
 * book this screen offers cannot be one the server then refuses on the
 * identity, and one it blocks cannot be one the server would have taken. */
const RUNG_TOLERANCE = 1e-9;

/** spec section 7: `paid_in + unfunded = committed + cumulative_recycled`.
 * Deliberately NOT the simpler `paid_in + unfunded = committed`, which
 * recycling legitimately breaks — the same note `ah/port/book.py` carries. */
function recyclingIdentityHolds(book: Book): boolean {
  return Object.values(book.private)
    .flat()
    .every((r) => {
      const lhs = r.commitment.paid_in + r.commitment.unfunded;
      const rhs = r.commitment.committed + r.commitment.cumulative_recycled;
      return Math.abs(lhs - rhs) <= RUNG_TOLERANCE;
    });
}

export function BookEntry({
  runId,
  initialBook,
  initialPlan,
  onReady,
  onCancel,
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
}) {
  const [resp, setResp] = useState<DefaultBookResponse | null>(null);
  const [book, setBook] = useState<Book | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  /** the band inputs, as typed. `book.ranges` is derived from this on every
   * edit — it is the posted document, this is the editing surface. */
  const [rangeText, setRangeText] = useState<Record<string, RangeText>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDefaultBook(runId)
      .then((r) => {
        if (cancelled) return;
        const seeded = deepClone(initialBook ?? r.book);
        setResp(r);
        setBook(seeded);
        setPlan(deepClone(initialPlan ?? r.plan));
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
  // the policy side, computed exactly like the book side and never mixed with
  // it: `sum(targets) + cash` is the denominator a target's implied weight is
  // measured against, and the values' own total is the denominator the HELD
  // weight is measured against. While the targets are mid-edit those two
  // denominators differ, which is precisely when the readout earns its place.
  const targets = book ? shownTargets(book) : {};
  const values = book ? sleeveValues(book) : {};
  const policyBase = book ? Object.values(targets).reduce((a, b) => a + b, 0) + book.cash : NaN;
  const policyWeight = (sleeve: string) => ((targets[sleeve] ?? NaN) / policyBase) * 100;
  const heldWeight = (sleeve: string) => ((values[sleeve] ?? NaN) / total) * 100;
  const drift = (sleeve: string) => heldWeight(sleeve) - policyWeight(sleeve);
  // Each refusal the SERVER can raise on shape gets its own named check, so
  // the panel can say which one is blocking rather than only that something
  // is (spec section 6's validity panel).
  // A blank field makes every OTHER rule false as well (NaN fails each
  // comparison), so it is reported alone rather than alongside three
  // consequences of itself.
  const shapeFaults: string[] = [];
  if (book && plan) {
    if (!allFieldsFinite(book, plan)) {
      shapeFaults.push("a field is blank or not a number");
    } else {
      if (!allFieldsNonNegative(book, plan)) shapeFaults.push("a field is negative");
      if (!recyclingIdentityHolds(book)) {
        shapeFaults.push("a rung breaks paid_in + unfunded = committed + recycled");
      }
      if (Math.abs(total - 100) > 0.01) shapeFaults.push("the book does not total 100");
      // the targets obey the SAME identity as the values, on the same
      // tolerance — an institution's policy allocation and its cash have to
      // add up to the whole institution. Reported separately from the book
      // total so the analyst is told which of the two is off.
      //
      // Guarded on targets being PRESENT: with none entered they fall back to
      // the values, and both checks would then restate the two above them
      // word for word against the same numbers. A retained `opening-book-0.1`
      // book is the only way to reach that.
      if (book.targets) {
        if (Object.values(targets).some((t) => t < 0)) shapeFaults.push("a target is negative");
        if (Math.abs(policyBase - 100) > 0.01) shapeFaults.push("the targets do not total 100");
      }
      shapeFaults.push(...rangeFaults(rangeText));
    }
  }
  const ready = !!book && !!plan && shapeFaults.length === 0;

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

  const setPlanPoint = (sleeve: string, i: number, value: number) =>
    setPlan((p) => {
      if (!p) return p;
      const points = p.points[sleeve].map((v, idx) => (idx === i ? value : v));
      return { ...p, points: { ...p.points, [sleeve]: points } };
    });

  const resetPlan = () => setPlan(deepClone(resp.plan));

  const planYears = plan.points[privateSleeves[0]] ?? [];

  return (
    <main className="shell book-entry">
      <h1>Enter the opening book</h1>
      <p className="tagline">
        Pre-filled with today&apos;s derived book. Edit only what your institution
        actually holds — everything else stays on the plan.
      </p>

      <section className="setup book-liquid">
        <h2>Liquid sleeves</h2>
        <p className="book-note">
          <strong>Value</strong> is what you hold today. <strong>Target</strong> is your
          policy allocation, and it is what the commitment programme paces
          against. The <strong>band</strong> is optional and{" "}
          <strong>reports only</strong> — nothing rebalances to it.
        </p>
        <div className="policy-grid">
          <div className="policy-head">
            <span>sleeve</span>
            <span>value</span>
            <span>target</span>
            <span>policy wt</span>
            <span>drift</span>
            <span>band lo</span>
            <span>band hi</span>
          </div>
          {resp.liquid_sleeves.map((sleeve) => (
            <div key={sleeve} className="policy-row">
              <span className="policy-name">{sleeve}</span>
              <input
                type="number"
                aria-label={sleeve}
                value={Number.isFinite(book.liquid[sleeve]) ? book.liquid[sleeve] : ""}
                onChange={(e) => setLiquid(sleeve, Number(e.target.value))}
              />
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
          ))}
          <div className="policy-row">
            <span className="policy-name">cash</span>
            <input
              type="number"
              aria-label="cash"
              value={Number.isFinite(book.cash) ? book.cash : ""}
              onChange={(e) => setCash(Number(e.target.value))}
            />
            <span className="policy-residual">
              cash is the residual — it carries no target and no band
            </span>
          </div>
        </div>
      </section>

      {privateSleeves.map((sleeve) => (
        <section key={sleeve} className="book-ladder">
          <div className="book-ladder-head">
            <h2>{sleeve}</h2>
            <button type="button" onClick={() => resetSleeve(sleeve)}>
              {`Reset ${sleeve}`}
            </button>
          </div>
          {/* a private sleeve's policy line: ONE target and ONE band for the
              whole sleeve, not per rung. Its held value is the ladder below
              summed at nav_true, which is what the drift is measured on. */}
          <div className="policy-strip">
            <label className="pcell">
              <span className="pk">target</span>
              <input
                type="number"
                aria-label={`${sleeve} target`}
                value={Number.isFinite(targets[sleeve]) ? targets[sleeve] : ""}
                onChange={(e) => setTarget(sleeve, Number(e.target.value))}
              />
            </label>
            <span className="pcell">
              <span className="pk">policy wt</span>
              <span className="policy-wt" data-testid={`target-weight-${sleeve}`}>
                {fmt1(policyWeight(sleeve))}%
              </span>
            </span>
            <span className="pcell">
              <span className="pk">drift</span>
              <span
                className={`policy-drift${Math.abs(drift(sleeve)) < 0.05 ? " flat" : ""}`}
                data-testid={`target-drift-${sleeve}`}
              >
                {signed(drift(sleeve))}
              </span>
            </span>
            <span className="pcell pband">
              <span className="pk">band lo / hi</span>
              <span className="pband-inputs">{bandInputs(sleeve)}</span>
            </span>
          </div>
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
                  <tr key={i}>
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

      <section className="book-plan">
        <div className="book-ladder-head">
          <h2>Commitment plan</h2>
          <button type="button" onClick={resetPlan}>
            Reset plan
          </button>
        </div>
        <div className="book-ladder-scroll">
          <table>
            <thead>
              <tr>
                <th>year</th>
                {privateSleeves.map((s) => (
                  <th key={s}>{s}</th>
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

      <div className="book-rail">
        <div>
          <span className="k">Total</span>
          <span className="v" data-testid="book-total">
            {Number.isFinite(totalRounded) ? totalRounded : "—"}
          </span>
        </div>
        <div>
          <span className="k">Targets + cash</span>
          <span className="v" data-testid="targets-total">
            {Number.isFinite(policyBase) ? Math.round(policyBase * 100) / 100 : "—"}
          </span>
        </div>
      </div>

      {shapeFaults.length > 0 && (
        <p className="book-note error" data-testid="shape-faults">
          {shapeFaults.join("; ")}
        </p>
      )}

      <p className="book-note" data-testid="ranked-note">
        {isDefault
          ? "Ranked is available — this is the default book."
          : "Practice only — you have edited the book."}
      </p>

      <button disabled={!ready} onClick={() => onReady(book, plan, isDefault)}>
        Continue
      </button>
      <button onClick={onCancel}>back</button>
    </main>
  );
}
