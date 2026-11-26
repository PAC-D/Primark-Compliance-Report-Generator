"use client";

import type { RefObject } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";

/** Carton Connect's motion rules: motion marks arrival or change only, 150–250 ms, and nothing moves under reduced motion. */
export const prefersReducedMotion = (): boolean =>
  typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Page arrival: the scope's [data-arrive] children fade and rise in, staggered. useGSAP runs before paint, so they
 *  never show first and then vanish. Re-runs when deps change (e.g. once the data has loaded and the sections exist),
 *  but only new sections animate: one that has arrived is marked data-arrived and left alone. */
export function useArrival(scope: RefObject<HTMLElement | null>, deps: unknown[] = []) {
  useGSAP(
    () => {
      if (prefersReducedMotion() || !scope.current) return;
      const items = [...scope.current.querySelectorAll("[data-arrive]:not([data-arrived])")];
      if (!items.length) return;
      items.forEach((e) => e.setAttribute("data-arrived", ""));
      gsap.fromTo(items, { opacity: 0, y: 8 }, {
        opacity: 1, y: 0, duration: 0.2, ease: "power2.out", stagger: 0.04, immediateRender: true, clearProps: "opacity,transform",
      });
    },
    { scope, dependencies: deps },
  );
}

/** First view of a Recharts chart: solid lines draw in, bars grow from the axis, dotted lines fade in.
 *  The chart is visible by default: the start state is only set at the moment it comes into view (and it does nothing
 *  without IntersectionObserver, in a hidden tab, or under reduced motion). Printing jumps to the end. */
export function useChartDraw(scope: RefObject<HTMLElement | null>) {
  useGSAP(
    (_, contextSafe) => {
      const el = scope.current;
      if (prefersReducedMotion() || !el || !contextSafe || typeof IntersectionObserver === "undefined" || document.hidden) return;
      let tl: gsap.core.Timeline | undefined;
      let mo: MutationObserver | undefined;
      const draw = contextSafe((): boolean => {
        const lines = [...el.querySelectorAll<SVGPathElement>("path.recharts-line-curve:not([stroke-dasharray])")];
        const dotted = el.querySelectorAll("path.recharts-line-curve[stroke-dasharray]");
        const bars = el.querySelectorAll(".recharts-bar-rectangle");
        if (!lines.length && !dotted.length && !bars.length) return false;
        // pathLength=1 makes the dash maths independent of the chart's size, which can change while it draws
        lines.forEach((p) => p.setAttribute("pathLength", "1"));
        tl = gsap.timeline({ defaults: { duration: 0.25, ease: "power2.out", immediateRender: true } });
        if (lines.length)
          tl.fromTo(lines, { strokeDasharray: 1, strokeDashoffset: 1 }, { strokeDashoffset: 0, clearProps: "strokeDasharray,strokeDashoffset" }, 0);
        if (dotted.length) tl.fromTo(dotted, { opacity: 0 }, { opacity: 1, clearProps: "opacity" }, 0);
        if (bars.length)
          tl.fromTo(bars, { scaleY: 0, transformOrigin: "50% 100%" }, { scaleY: 1, stagger: 0.01, clearProps: "transform" }, 0);
        return true;
      });
      // Recharts draws its marks after it has measured the container: if they aren't there yet, wait for them
      // (a MutationObserver runs before paint, so they never show first and then vanish)
      const start = () => {
        if (draw()) return;
        mo = new MutationObserver(() => draw() && mo?.disconnect());
        mo.observe(el, { childList: true, subtree: true });
      };
      const io = new IntersectionObserver(([e]) => {
        if (!e.isIntersecting) return;
        io.disconnect();
        start();
      });
      const r = el.getBoundingClientRect();
      if (r.width && r.bottom > 0 && r.top < window.innerHeight) start(); // already in view: start before the first paint
      else io.observe(el);
      const finish = () => tl?.progress(1);
      window.addEventListener("beforeprint", finish);
      return () => {
        io.disconnect();
        mo?.disconnect();
        window.removeEventListener("beforeprint", finish);
      };
    },
    { scope },
  );
}
