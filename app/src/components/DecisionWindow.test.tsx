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
    render(<DecisionWindow month={11} year={1} onCommit={onCommit} />);
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
    render(<DecisionWindow month={11} year={1} onCommit={() => {}} />);
    const labels = [...host!.querySelectorAll(".action-card strong")].map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["Hold course", "De-risk", "Lean in", "Secondary sale"]);
  });
});
