"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { MonthPicker } from "@/components/MonthPicker";
import { Button } from "@/components/ui/button";
import { apiGet, fileUrl } from "@/lib/api";
import { useDownload } from "@/lib/download";
import { useArrival } from "@/lib/motion";
import { monthName, readFilters, supplierPath } from "@/lib/query";
import { cn } from "@/lib/utils";
import { Rate, Section } from "../dashboard/parts";
import type { Dashboard } from "../dashboard/types";
import { Report } from "./Report";
import { Search } from "./Search";
import { Transactions } from "./Transactions";
import type { SupplierReport } from "./types";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** One supplier's PDF on screen, chosen by search; with none chosen, the month's suppliers needing follow-up. */
function SupplierCompliancePage() {
  const router = useRouter();
  const search = useSearchParams();
  const f = useMemo(() => readFilters(new URLSearchParams(search.toString())), [search]);
  const supplier = f.supplier;

  const [latest, setLatest] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const month = f.month || latest;
  const go = (name: string, m: string | null = f.month || null) => router.push(supplierPath(name, m), { scroll: false });

  useEffect(() => {
    apiGet<{ month: string }>("/latest-month").then((r) => setLatest(r.month), (e) => setProblem(message(e)));
  }, []);

  return (
    <section className="flex flex-col gap-3.5">
      <div className="head">
        <div>
          <h1>Supplier Compliance</h1>
          <p>{month ? `The supplier report for ${monthName(month)}` : "Loading"}</p>
        </div>
        <div className="act">
          <MonthPicker latest={latest} value={month} onChange={(m) => go(supplier, m)} />
        </div>
      </div>
      <div className="relative z-20 max-w-xl"><Search month={month} onPick={(s) => go(s)} /></div>
      {problem && <p className="text-danger" role="alert">{problem}</p>}
      {month && (supplier
        ? <SupplierView key={supplier} supplier={supplier} month={month} />
        : <FollowUpLinks month={month} />)}
    </section>
  );
}

/** The chosen supplier: its report (dimmed while another month loads), transactions and downloads. */
function SupplierView({ supplier, month }: { supplier: string; month: string }) {
  const [loaded, setLoaded] = useState<{ month: string; d: SupplierReport } | null>(null); // labels and links follow the loaded month
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<string | null>(null);
  const pdf = useDownload();
  const data = useDownload();
  const scope = useRef<HTMLDivElement>(null);
  useArrival(scope, [!!loaded]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setProblem(null);
    apiGet<SupplierReport>("/supplier", { supplier, month })
      .then((d) => live && setLoaded({ month, d }), (e) => {
        if (!live) return;
        setLoaded(null); // never leave another month's figures under an error
        setProblem(message(e)); // a 404 says "No lines for this supplier in <Month Year>."
      })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [supplier, month]);

  if (problem) return <p className="text-danger" role="alert">{problem}</p>;
  if (!loaded) return <p className="text-ink2">Loading {supplier}…</p>;
  const m = loaded.month;
  const file = `${supplier.replace(/[<>:"/\\|?*]/g, "_")}_${monthName(m).replace(" ", "_")}`; // Windows-safe fallback name

  return (
    <div ref={scope} aria-busy={loading} className={cn("flex flex-col gap-3.5 transition-opacity duration-200", loading && "opacity-50")}>
      <div data-arrive className="flex flex-wrap justify-end gap-2.5">
        <Button variant="secondary" disabled={data.busy} onClick={() => data.start(fileUrl("/supplier-data", { supplier, month: m }), `${file}.xlsx`)}>
          {data.busy ? "Preparing…" : "Download data"}
        </Button>
        <Button disabled={pdf.busy} onClick={() => pdf.start(fileUrl("/supplier-pdf", { supplier, month: m }), `${file}.pdf`)}>
          {pdf.busy ? "Preparing…" : "Download PDF"}
        </Button>
      </div>
      <Report d={loaded.d} />
      <Transactions key={m} supplier={supplier} month={m} />
    </div>
  );
}

/** With no supplier chosen: the month's Follow-Up Required suppliers, as a place to start. */
function FollowUpLinks({ month }: { month: string }) {
  const [loaded, setLoaded] = useState<{ month: string; rows: Dashboard["suppliers_below"] } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const scope = useRef<HTMLDivElement>(null);
  useArrival(scope, [!!loaded]);

  useEffect(() => {
    let live = true;
    setProblem(null);
    apiGet<Dashboard>("/dashboard", { month })
      .then((d) => live && setLoaded({ month, rows: d.suppliers_below }), (e) => {
        if (!live) return;
        setLoaded(null);
        setProblem(message(e));
      });
    return () => { live = false; };
  }, [month]);

  if (problem) return <p className="text-danger" role="alert">{problem}</p>;
  return (
    <div ref={scope} className={cn("transition-opacity duration-200", loaded?.month !== month && "opacity-50")}>
      <Section title="Follow-up required" caption={loaded ? `Below 40% this month and on the 3-month average · ${monthName(loaded.month)}` : "Loading"}>
        {loaded && loaded.rows.length === 0 && <p className="px-4.5 text-ink2">No supplier needs follow-up this month.</p>}
        <ul className="border-t border-line">
          {loaded?.rows.map((s) => (
            <li key={s.supplier} className="border-b border-line2 last:border-b-0">
              <Link href={supplierPath(s.supplier, loaded.month)}
                className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5 px-4.5 py-2.5 hover:bg-surface2">
                <span className="mr-auto font-medium">{s.supplier}</span>
                <span className="text-xs text-ink2">This month <Rate value={s.compliance_rate} /></span>
                <span className="text-xs text-ink2">3-month avg <Rate value={s.avg_3month} /></span>
              </Link>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

export default function Page() {
  return <Suspense><SupplierCompliancePage /></Suspense>;
}
