"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { BASE } from "@/lib/api";
import { applyTheme, readTheme, type Theme } from "@/lib/theme";
import { Seg } from "./Seg";

export const TABS = [
  { href: "/", label: "Dashboard" },
  { href: "/supplier-compliance", label: "Supplier Compliance" },
  { href: "/kpi", label: "KPI" },
  { href: "/reports", label: "Reports" },
  { href: "/data", label: "Data" },
  { href: "/suppliers", label: "Suppliers" },
];

const isActive = (path: string, href: string) => (href === "/" ? path === "/" : path.startsWith(href));

/** The tabs. Each link carries the current ?month= so the month survives a tab change. The active pill slides
 *  between tabs (a CSS transition, so reduced motion stops it). */
function Nav({ month }: { month: string }) {
  const path = usePathname();
  const nav = useRef<HTMLElement>(null);
  const pill = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const place = () => {
      const a = nav.current?.querySelector<HTMLElement>("a[aria-current]");
      const p = pill.current;
      if (!p) return;
      p.style.opacity = a ? "1" : "0";
      if (a) {
        p.style.width = `${a.offsetWidth}px`;
        p.style.transform = `translateX(${a.offsetLeft}px)`;
      }
    };
    place();
    const ro = new ResizeObserver(place); // the font loading or the window resizing changes the tab widths
    if (nav.current) ro.observe(nav.current);
    // slide only after the first placement: the pill arrives in place, it moves on change
    const id = requestAnimationFrame(() => pill.current?.setAttribute("data-ready", ""));
    return () => {
      ro.disconnect();
      cancelAnimationFrame(id);
    };
  }, [path]);
  const q = month ? `?month=${encodeURIComponent(month)}` : "";
  return (
    <nav className="navtrack" aria-label="Main" ref={nav}>
      <span className="navpill" ref={pill} aria-hidden="true" />
      {TABS.map((t) => (
        <Link key={t.href} href={t.href + q} aria-current={isActive(path, t.href) ? "page" : undefined}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

function NavWithMonth() {
  return <Nav month={useSearchParams().get("month") ?? ""} />;
}

const THEMES: { key: Theme; label: string }[] = [
  { key: "light", label: "Light" },
  { key: "system", label: "System" },
  { key: "dark", label: "Dark" },
];

/** The frosted 56px top bar: the two original logos, the tabs, and the avatar menu with Light / System / Dark. */
export function TopBar() {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>("system");
  const end = useRef<HTMLDivElement>(null);
  const avatar = useRef<HTMLButtonElement>(null);

  useEffect(() => setTheme(readTheme()), []);
  useEffect(() => {
    if (!open) return;
    // A disclosure: the panel follows the button, so Tab walks into it. Escape closes it and puts focus back on the
    // avatar; a click or focus anywhere else closes it.
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent) {
        if (e.key !== "Escape") return;
        setOpen(false);
        avatar.current?.focus();
      } else if (!end.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    document.addEventListener("focusin", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
      document.removeEventListener("focusin", close);
    };
  }, [open]);

  const pick = (t: Theme) => {
    setTheme(t);
    applyTheme(t);
  };

  return (
    <header className="topbar">
      <div className="logos">
        {/* each logo opens its company's site in a new tab, as in Carton Connect */}
        <a href="https://allportcs.com/pac-d/" target="_blank" rel="noopener">
          <img className="logo-pacd" src={`${BASE}/brand/pacd-logo.png`} alt="PAC-D website" width={572} height={190} />
        </a>
        <span className="logo-divider" aria-hidden="true" />
        <a href="https://www.primark.com/" target="_blank" rel="noopener" className="logo-primark-link">
          <img className="logo-primark" src={`${BASE}/brand/primark-logo.png`} alt="Primark website" width={2285} height={311} />
        </a>
      </div>
      {/* useSearchParams needs a Suspense boundary to prerender; the fallback is the same tabs without the month */}
      <Suspense fallback={<Nav month="" />}>
        <NavWithMonth />
      </Suspense>
      <div className="topbar-end" ref={end}>
        <button ref={avatar} type="button" className="avatar" aria-label="Account and appearance" aria-expanded={open}
          aria-controls="account-menu" onClick={() => setOpen(!open)}>
          CT
        </button>
        {open && (
          <div className="menu" id="account-menu">
            <div className="who">
              <span className="avatar" aria-hidden="true">CT</span>
              <div><b>Compliance team</b><span>PAC-D · TPS compliance</span></div>
            </div>
            <div className="menu-label" aria-hidden="true">Appearance</div>
            <Seg label="Appearance" items={THEMES} value={theme} onChange={pick} />
          </div>
        )}
      </div>
    </header>
  );
}
