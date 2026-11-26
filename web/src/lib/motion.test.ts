import { afterEach, describe, expect, it, vi } from "vitest";

const tweens = vi.hoisted(() => ({ from: vi.fn(), to: vi.fn(), fromTo: vi.fn(), set: vi.fn(), timeline: vi.fn() }));
vi.mock("gsap", () => ({ default: tweens, gsap: tweens }));
// useGSAP runs its callback straight away, so the hook can be called outside React.
vi.mock("@gsap/react", () => ({ useGSAP: (fn: (ctx: unknown, safe: <F>(f: F) => F) => void) => fn({}, (f) => f) }));

import { prefersReducedMotion, useArrival, useChartDraw } from "./motion";

function stubMotion(reduce: boolean) {
  vi.stubGlobal("window", {
    matchMedia: (q: string) => ({ matches: reduce && q === "(prefers-reduced-motion: reduce)", media: q }),
  });
}

/** A scope with two children; querySelectorAll honours :not([data-arrived]). */
function scope() {
  const kids = [0, 1].map(() => {
    const attrs = new Set<string>();
    return { attrs, setAttribute: vi.fn((a: string) => attrs.add(a)), getAttribute: () => null };
  });
  const el = {
    kids,
    querySelectorAll: (sel: string) => (sel.includes(":not([data-arrived])") ? kids.filter((k) => !k.attrs.has("data-arrived")) : kids),
    getBoundingClientRect: () => ({ width: 100, top: 0, bottom: 100 }),
  };
  return el as unknown as HTMLElement & { kids: typeof kids };
}

describe("motion", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("under reduced motion nothing moves", () => {
    stubMotion(true);
    expect(prefersReducedMotion()).toBe(true);
    useArrival({ current: scope() });
    useChartDraw({ current: scope() });
    for (const fn of Object.values(tweens)) expect(fn).not.toHaveBeenCalled();
  });

  it("sections arrive once: a re-run leaves arrived sections alone", () => {
    stubMotion(false);
    expect(prefersReducedMotion()).toBe(false);
    const el = scope();
    useArrival({ current: el });
    expect(tweens.fromTo).toHaveBeenCalledOnce();
    expect(tweens.fromTo.mock.calls[0][2]).toMatchObject({ opacity: 1, y: 0, immediateRender: true });
    useArrival({ current: el });
    expect(tweens.fromTo).toHaveBeenCalledOnce();
  });

  it("without IntersectionObserver a chart is left untouched (visible)", () => {
    stubMotion(false);
    const el = scope();
    useChartDraw({ current: el });
    for (const fn of Object.values(tweens)) expect(fn).not.toHaveBeenCalled();
    for (const k of el.kids) expect(k.setAttribute).not.toHaveBeenCalled();
  });
});
