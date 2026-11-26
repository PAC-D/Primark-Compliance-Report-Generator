"use client";

import { useEffect, useState } from "react";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { apiGet } from "@/lib/api";
import type { SearchResult } from "./types";

type Factory = SearchResult["factories"][number];

/** Supplier and factory names with lines in the month (GET /api/search, 250 ms after typing stops).
 *  Picking a supplier calls onPick; picking a factory lists its suppliers to pick from. */
export function Search({ month, onPick }: { month: string | null; onPick: (supplier: string) => void }) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<{ q: string; month: string; r: SearchResult } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [factory, setFactory] = useState<Factory | null>(null);
  const [active, setActive] = useState(""); // the highlighted item, so Enter works after switching lists
  const text = q.trim();

  useEffect(() => {
    setFactory(null);
    setProblem(null); // a new search: the last one's error no longer applies
    setFound(null); // nor its results (another month's names may have no lines in this one)
    if (!month || !text) return;
    let live = true;
    const t = setTimeout(() => {
      apiGet<SearchResult>("/search", { month, q: text }).then(
        (r) => { if (live) { setFound({ q: text, month, r }); setProblem(null); } },
        (e) => { if (live) { setFound(null); setProblem(e instanceof Error ? e.message : String(e)); } },
      );
    }, 250);
    return () => { live = false; clearTimeout(t); };
  }, [month, text]);

  const openFactory = (f: Factory | null, back?: string) => {
    setFactory(f);
    setActive(f ? `p:${f.suppliers[0]}` : `f:${back}`);
  };
  const pick = (name: string) => {
    setQ("");
    onPick(name);
  };
  const open = !!text;
  const r = found?.q === text && found.month === month ? found.r : null; // never older text's or another month's results

  return (
    <Command shouldFilter={false} value={active} onValueChange={setActive} className="relative overflow-visible! bg-transparent p-0"
      onKeyDown={(e) => { if (e.key === "Escape") setQ(""); }}>
      <CommandInput value={q} onValueChange={setQ} placeholder="Search a supplier or factory" aria-label="Search a supplier or factory" disabled={!month}
        className="h-9" />
      {open && (
        <CommandList className="absolute top-full right-0 left-0 z-30 mt-1 rounded-xl bg-popover p-1 shadow-(--pop)">
          {problem && <div role="alert" className="px-2 py-3 text-danger">{problem}</div>}
          {!problem && !r && <div className="px-2 py-3 text-ink2">Searching…</div>}
          {r && !factory && (
            <>
              <CommandEmpty>No supplier or factory with lines this month matches.</CommandEmpty>
              {r.suppliers.length > 0 && (
                <CommandGroup heading="Suppliers">
                  {r.suppliers.map((s) => <CommandItem key={s} value={`s:${s}`} onSelect={() => pick(s)}>{s}</CommandItem>)}
                </CommandGroup>
              )}
              {r.factories.length > 0 && (
                <CommandGroup heading="Factories">
                  {r.factories.map((f) => (
                    <CommandItem key={f.factory} value={`f:${f.factory}`} onSelect={() => openFactory(f)}>
                      <span className="min-w-0 truncate">{f.factory}</span>
                      <span className="ml-auto shrink-0 text-xs text-ink2">{f.suppliers.length} supplier{f.suppliers.length === 1 ? "" : "s"}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
            </>
          )}
          {r && factory && (
            <CommandGroup heading={`Suppliers at ${factory.factory}`}>
              {factory.suppliers.map((s) => <CommandItem key={s} value={`p:${s}`} onSelect={() => pick(s)}>{s}</CommandItem>)}
              <CommandItem value="back" onSelect={() => openFactory(null, factory.factory)} className="text-ink2">Back to results</CommandItem>
            </CommandGroup>
          )}
        </CommandList>
      )}
    </Command>
  );
}
