/**
 * su-app-02 acceptance: E1's commitment affordance.
 *
 * The register row's requirement, tested at the surface that implements it:
 * NOTHING commits until the player chooses — hold is an explicit selection
 * with the same weight as acting, never a click-through default.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionWindow } from "./DecisionWindow";

let root: Root | null = null;
let host: HTMLElement | null = null;

function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(ui));
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
});

describe("DecisionWindow (E1)", () => {
  it("commit is disabled until an action is explicitly chosen — hold included", () => {
    const onCommit = vi.fn();
    render(<DecisionWindow open month={11} year={1} onCommit={onCommit} />);
    const commit = host!.querySelector<HTMLButtonElement>("button.commit")!;
    expect(commit.disabled).toBe(true);
    act(() => commit.click());
    expect(onCommit).not.toHaveBeenCalled();

    // choosing HOLD is a commitment, not a default
    const hold = host!.querySelector<HTMLInputElement>('input[type="radio"]')!;
    act(() => hold.click());
    expect(commit.disabled).toBe(false);
    act(() => commit.click());
    expect(onCommit).toHaveBeenCalledTimes(1);
    const [action, timeOnWindow] = onCommit.mock.calls[0];
    expect(action).toBe("hold");
    expect(typeof timeOnWindow).toBe("number");
  });

  it("all four actions are on the card", () => {
    render(<DecisionWindow open month={11} year={1} onCommit={() => {}} />);
    const labels = [...host!.querySelectorAll(".action-card strong")].map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["Hold course", "De-risk", "Lean in", "Secondary sale"]);
  });

  it("sends ONLY the sleeves the player touched, so the rest stay exactly on plan", () => {
    /**
     * Audit F4. The pre-fill is the plan as at the last CLOSED quarter, while
     * the engine commits on the weight at the commitment quarter — up to 7.9%
     * apart, and unfixable here because that quarter's returns are unrevealed
     * (computing the pre-fill from them would leak the tape).
     *
     * The old lever merged the whole pre-fill into its state as soon as ONE
     * sleeve was edited, so touching pe silently froze pc and re at stale
     * numbers the player believed were "the plan". Sending only what was
     * touched makes the untouched sleeves fall through to the server's own
     * fresh computation, which is the exact plan.
     */
    const onCommit = vi.fn();
    const plan = { pe: 1.5, pc: 1.2, re: 0.9 };
    render(
      <DecisionWindow
        open
        month={11}
        year={1}
        onCommit={onCommit}
        planCommitments={plan}
        planBasis={{ as_of_quarter: 3, as_of_month: 11, private_weight_reported: 0.31 }}
      />,
    );
    const inputs = [...host!.querySelectorAll<HTMLInputElement>(".lever-row input")];
    expect(inputs.map((i) => i.value)).toEqual(["1.50", "1.20", "0.90"]);

    // edit ONE sleeve
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      )!.set!;
      setter.call(inputs[0], "2.00");
      inputs[0].dispatchEvent(new Event("input", { bubbles: true }));
    });

    act(() => host!.querySelector<HTMLInputElement>('input[type="radio"]')!.click());
    act(() => host!.querySelector<HTMLButtonElement>("button.commit")!.click());

    const commitments = onCommit.mock.calls[0][2];
    expect(commitments).toEqual({ pe: 2 });
    expect(commitments).not.toHaveProperty("pc");
    expect(commitments).not.toHaveProperty("re");
  });

  it("declares the state the pre-fill was computed from", () => {
    render(
      <DecisionWindow
        open
        month={11}
        year={1}
        onCommit={() => {}}
        planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9 }}
        planBasis={{ as_of_quarter: 3, as_of_month: 11, private_weight_reported: 0.31 }}
      />,
    );
    const note = host!.querySelector(".lever-basis")!.textContent!;
    expect(note).toContain("month 11");
  });

  it("shows the pacing rule's number beside the plan's, labelled and not applied", () => {
    /**
     * su-app-06 sections 4.3 and 6 (C2). The server has served `plan_pace`
     * since task 6 and nothing rendered it, so the pacing flex went from
     * silently APPLIED to silently INVISIBLE. It must appear beside each
     * sleeve's plan figure, labelled as the pacing rule's view.
     *
     * Asserting the label exists is not enough — a render that put the
     * pacing number INTO the input would also produce a label. The input's
     * value is checked here too: what the lever will commit stays the plan.
     */
    render(
      <DecisionWindow
        open
        month={11}
        year={1}
        onCommit={() => {}}
        planCommitments={{ pe: 5, pc: 1.2, re: 0.9 }}
        planPace={{ pe: 3.18, pc: 1.44, re: 1.26 }}
      />,
    );
    const rows = [...host!.querySelectorAll(".lever-row")];
    expect(rows[0].querySelector(".lever-plan")!.textContent).toContain("5.00");
    expect(rows[0].querySelector(".lever-pace")!.textContent).toMatch(/pacing rule\s+3\.18/);
    expect(rows[1].querySelector(".lever-pace")!.textContent).toMatch(/1\.44/);
    // the committed number is the PLAN's, not the pacing rule's
    expect(rows[0].querySelector("input")!.value).toBe("5.00");
  });

  it("explains the plan-carrying session, where the F4 caveat is suppressed", () => {
    /**
     * The server sets `next_plan_basis` to null for plan-carrying sessions
     * (nothing is approximated), which switched OFF the only paragraph the
     * lever had. Those sessions were left with no explanation at all. The
     * plan-carrying explanation replaces it; the F4 caveat still governs
     * sessions without a plan (covered by the test above).
     */
    render(
      <DecisionWindow
        open
        month={11}
        year={1}
        onCommit={() => {}}
        planCommitments={{ pe: 5, pc: 1.2, re: 0.9 }}
        planBasis={null}
        planPace={{ pe: 3.18, pc: 1.44, re: 1.26 }}
      />,
    );
    expect(host!.querySelector(".lever-basis")).toBeNull();
    const note = host!.querySelector(".lever-plan-note")!.textContent!;
    expect(note).toMatch(/leave alone commits exactly what is shown/i);
  });

  it("a session with no plan gets neither the pacing column nor the plan note", () => {
    // the Task 6 scope fence at the surface: no stored plan => no plan_pace,
    // and the F4 caveat is the paragraph that governs.
    render(
      <DecisionWindow
        open
        month={11}
        year={1}
        onCommit={() => {}}
        planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9 }}
        planBasis={{ as_of_quarter: 3, as_of_month: 11, private_weight_reported: 0.31 }}
      />,
    );
    expect(host!.querySelectorAll(".lever-pace").length).toBe(0);
    expect(host!.querySelector(".lever-plan-note")).toBeNull();
    expect(host!.querySelector(".lever-basis")).not.toBeNull();
  });

  it("the four levers stay on the main page between windows, inert", () => {
    const onCommit = vi.fn();
    render(
      <DecisionWindow open={false} month={23} year={2} nextYear={2} onCommit={onCommit} />,
    );
    const labels = [...host!.querySelectorAll(".action-card strong")].map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["Hold course", "De-risk", "Lean in", "Secondary sale"]);
    // visible, but there is nothing to commit and nothing to select
    expect(host!.querySelector("button.commit")).toBeNull();
    expect(host!.querySelectorAll('input[type="radio"]').length).toBe(0);
    expect(host!.querySelectorAll(".action-card.inert").length).toBe(4);
    expect(onCommit).not.toHaveBeenCalled();
  });
});
