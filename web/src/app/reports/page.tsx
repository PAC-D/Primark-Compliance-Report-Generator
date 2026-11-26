"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { JobStatus, startJob, type Job } from "@/components/JobStatus";
import { MonthPicker } from "@/components/MonthPicker";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, outputUrl } from "@/lib/api";
import { useDownload } from "@/lib/download";
import { int } from "@/lib/format";
import { useArrival } from "@/lib/motion";
import { monthFrom, monthName, withMonth } from "@/lib/query";
import { cn } from "@/lib/utils";
import { Section } from "../dashboard/parts";

type Item = { count: number; updated: string; folder?: string; file?: string } | null;
type Status = { total_suppliers: number; total_factories: number; outputs: Record<string, Item> };

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const stamp = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

const OUTPUTS = [
  { kind: "supplier-reports", label: "Supplier reports", unit: "PDFs" },
  { kind: "summary", label: "Summary workbook", unit: "" },
  { kind: "kpi", label: "KPI report", unit: "" },
  { kind: "extract", label: "Supplier data", unit: "workbooks" },
  { kind: "all-supplier-data", label: "All supplier data", unit: "" },
];

/** One output's Generate and Download buttons; Download shows "Preparing…" while the file is fetched. */
function Actions({ rel, busy, onGenerate }: { rel: string | null; busy: boolean; onGenerate: () => void }) {
  const dl = useDownload();
  return (
    <span className="inline-flex gap-2">
      <Button variant="secondary" onClick={onGenerate} disabled={busy}>Generate</Button>
      <Button variant="secondary" disabled={!rel || dl.busy} onClick={() => rel && dl.start(outputUrl(rel), rel.slice(rel.lastIndexOf("/") + 1))}>
        {dl.busy ? "Preparing…" : "Download"}
      </Button>
    </span>
  );
}

function ReportsPage() {
  const router = useRouter();
  const path = usePathname();
  const search = useSearchParams();
  const [latest, setLatest] = useState<string | null>(null);
  const month = useMemo(() => monthFrom(new URLSearchParams(search.toString())) ?? latest ?? "", [search, latest]); // the shared ?month=
  const setMonth = (m: string) => router.push(withMonth(path, m), { scroll: false });
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const startingNow = useRef(false);
  const [jobRunning, setJobRunning] = useState(false);
  const [zips, setZips] = useState<Record<string, string>>({});
  const [tick, setTick] = useState(0); // bump to reload the status, e.g. when a job ends
  const scope = useRef<HTMLElement>(null);
  useArrival(scope, [!!status]);

  useEffect(() => {
    apiGet<{ month: string }>("/latest-month").then((r) => setLatest(r.month), (e) => setProblem(message(e)));
  }, []);

  useEffect(() => {
    if (!month) return;
    let live = true;
    setLoading(true);
    setProblem(null);
    apiGet<Status>("/month-status", { month })
      .then(async (s) => {
        // the zips only exist after a full run, so ask before offering them (a one-byte read)
        const month_ = monthName(month).split(" ")[0];
        const y = month.slice(0, 4);
        const found: Record<string, string> = {};
        for (const [kind, prefix] of [["supplier-reports", "Supplier_Reports"], ["extract", "Supplier_Data"]]) {
          const folder = s.outputs[kind]?.folder;
          const rel = folder ? `${folder.slice(0, folder.lastIndexOf("/") + 1)}${prefix}_${month_}_${y}.zip` : null;
          const ok = rel ? (await fetch(outputUrl(rel), { headers: { Range: "bytes=0-0" } }).catch(() => null))?.ok : false;
          if (rel && ok) found[kind] = rel;
        }
        if (live) { setStatus(s); setZips(found); }
      }, (e) => { if (live) { setStatus(null); setProblem(message(e)); } })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [month, tick]);

  const generate = async (kind: string) => {
    if (!month || startingNow.current) return;
    startingNow.current = true;
    const body = new FormData();
    body.set("month", month);
    setStarting(true);
    const refused = await startJob(`/jobs/${kind}`, body);
    if (refused) toast.error("Could not start", { description: refused });
    setStarting(false);
    startingNow.current = false;
  };

  const onFinish = useCallback((j: Job) => {
    setTick((t) => t + 1);
    if (j.state === "done") toast.success(j.name, { description: j.result?.summary });
    else if (j.state === "failed") toast.error(j.name, { description: j.error || "The job failed." });
  }, []);
  const busy = starting || jobRunning || !month;

  return (
    <section ref={scope} className="flex flex-col gap-3.5">
      <div className="head">
        <div>
          <h1>Reports</h1>
          <p>{month ? monthName(month) : "Loading"}{status && ` · ${int(status.total_suppliers)} suppliers, ${int(status.total_factories)} factories`}</p>
        </div>
        <div className="act">
          <MonthPicker latest={latest} value={month || null} onChange={setMonth} />
        </div>
      </div>
      {problem && <p className="text-danger" role="alert">{problem}</p>}
      <JobStatus onFinish={onFinish} onUpdate={(j: Job | null) => setJobRunning(j?.state === "running")} />
      <Section title="Reports for the month" caption="Supplier reports and supplier data are folders of files; Download gives the zip from the last full run.">
        <div aria-busy={loading} className={cn("border-t border-line transition-opacity duration-200", loading && status && "opacity-50")}>
          <Table>
            <TableHeader>
              <TableRow><TableHead>Output</TableHead><TableHead>Status</TableHead><TableHead><span className="sr-only">Actions</span></TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {OUTPUTS.map((r) => {
                const it = status?.outputs[r.kind];
                const rel = it?.file ?? zips[r.kind] ?? null;
                return (
                  <TableRow key={r.kind}>
                    <TableCell>{r.label}</TableCell>
                    <TableCell>
                      {!status ? <span className="text-ink2">{loading ? "Loading" : "Unknown"}</span>
                        : !it ? <span className="text-ink2">Not generated</span>
                        : <>Generated {stamp(it.updated)}{r.unit && <span className="text-ink2"> · {int(it.count)} {r.unit}</span>}</>}
                    </TableCell>
                    <TableCell className="text-right"><Actions rel={rel} busy={busy} onGenerate={() => generate(r.kind)} /></TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </Section>
    </section>
  );
}

export default function Page() {
  return <Suspense><ReportsPage /></Suspense>;
}
