"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { startJob } from "@/components/JobStatus";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiGet, fileUrl } from "@/lib/api";
import { useDownload } from "@/lib/download";
import { int, points } from "@/lib/format";
import { addMonths, monthName, readFilters, type Band, type Filters } from "@/lib/query";
import { cn } from "@/lib/utils";
import { Rate, scroller, Section, SupplierLink } from "./parts";

/** GET /api/supplier-compliance (tps/metrics/dashboard.py::supplier_compliance): only what this table uses. */
type Supplier = {
  name: string; region: string; countries: string[]; factories: number; lines: number;
  compliance: number | null; band: Exclude<Band, "all">; avg_3m: number | null; change: number | null; rank: number | null;
};
type Data = { month: string; suppliers: Supplier[]; bands: Record<Band, number> };

const PAGE = 25;
const ANY = "any"; // a Select item can't have "" as its value
const BAND_TABS: { key: Band; label: string }[] = [
  { key: "all", label: "All" }, { key: "high", label: "70% and up" }, { key: "mid", label: "40–70%" }, { key: "low", label: "Below 40%" },
];
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Page numbers with gaps: 1 … 4 5 6 … 15. */
function pageList(page: number, pages: number): (number | null)[] {
  const keep = [...new Set([1, page - 1, page, page + 1, pages])].filter((p) => p >= 1 && p <= pages).sort((a, b) => a - b);
  return keep.flatMap((p, i) => (i && p - keep[i - 1] > 1 ? [null, p] : [p]));
}

/** The v1 all-supplier table: band counts, filters in the URL, tick boxes and bulk PDF / data downloads. */
export function AllSuppliers({ month, f, go, jobRunning, onJobProblem }: {
  month: string; f: Filters; go: (next: Filters) => void; jobRunning: boolean; onJobProblem: (p: string | null) => void;
}) {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<string | null>(null);
  const [countries, setCountries] = useState<string[]>([]);
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [starting, setStarting] = useState(false);
  const startingNow = useRef(false); // a double-click lands before the disabled state renders
  const zip = useDownload();

  useEffect(() => {
    let live = true;
    apiGet<{ countries: string[] }>("/options", { month })
      .then((o) => live && setCountries(o.countries), (e) => live && setProblem(message(e)));
    return () => { live = false; };
  }, [month]);

  useEffect(() => {
    let live = true;
    setProblem(null);
    setLoading(true);
    apiGet<Data>("/supplier-compliance", { month, region: f.region, country: f.country, supplier: f.supplier, factory: f.factory })
      .then((d) => live && setData({ ...d, month }), (e) => {
        if (!live) return;
        setData(null); // never leave the last filter's figures under an error
        setProblem(message(e));
      })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [month, f.region, f.country, f.supplier, f.factory]);

  // a new filter is a new list: ticks only carry across pages
  useEffect(() => setTicked(new Set()), [month, f.region, f.country, f.supplier, f.factory, f.band]);

  const rows = useMemo(() => (data?.suppliers ?? []).filter((s) => f.band === "all" || s.band === f.band), [data, f.band]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const page = Math.min(f.page, pages);
  const shown = rows.slice((page - 1) * PAGE, page * PAGE);
  const m = data?.month ?? month; // labels, links and downloads follow the rows on screen, not a month still loading

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const get = (k: string) => { const v = String(form.get(k) ?? "").trim(); return v === ANY ? "" : v; };
    go({ ...f, region: get("region"), country: get("country"), supplier: get("supplier"), factory: get("factory"), page: 1 });
  };
  const clear = () => go({ ...readFilters(new URLSearchParams()), month: f.month });

  const tick = (name: string) => setTicked((s) => { const n = new Set(s); if (!n.delete(name)) n.add(name); return n; });
  const allShown = shown.length > 0 && shown.every((r) => ticked.has(r.name));
  const tickShown = (on: boolean) => setTicked((s) => {
    const n = new Set(s);
    shown.forEach((r) => (on ? n.add(r.name) : n.delete(r.name)));
    return n;
  });

  const downloadPdfs = async () => {
    if (startingNow.current) return;
    startingNow.current = true;
    const body = new FormData();
    body.set("month", m);
    ticked.forEach((name) => body.append("supplier", name));
    setStarting(true);
    onJobProblem(await startJob("/jobs/supplier-reports", body));
    setStarting(false);
    startingNow.current = false;
  };
  const downloadData = () => {
    const q = new URLSearchParams({ month: m }); // one zip of the selected workbooks, `supplier` repeated
    ticked.forEach((name) => q.append("supplier", name));
    zip.start(`/api/supplier-data-zip?${q}`, `Supplier_Data_${monthName(m).replace(" ", "_")}.zip`);
  };

  const prev = monthName(addMonths(m, -1), { month: "short" });
  const R = "text-right";

  return (
    <Section title="All suppliers" caption={`${monthName(m)} · lowest compliance first`} className="overflow-visible">
      <div className="flex flex-col gap-3.5 px-4.5 pb-3.5">
        <Tabs value={f.band} onValueChange={(b) => go({ ...f, band: b as Band, page: 1 })} className="max-w-full overflow-x-auto overflow-y-hidden">
          <TabsList aria-label="Compliance band">
            {BAND_TABS.map((b) => (
              <TabsTrigger key={b.key} value={b.key}>
                {b.label}{data && <b className="font-semibold text-ink">{int(data.bands[b.key])}</b>}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        {/* keyed by the URL's filters, so Clear and back/forward reset what the fields show */}
        <form key={[f.region, f.country, f.supplier, f.factory].join("|")} onSubmit={submit}
          className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] items-end gap-x-3.5 gap-y-3">
          <Labelled label="Region">
            <Select name="region" defaultValue={f.region || ANY}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value={ANY}>Any</SelectItem><SelectItem value="BD">BD</SelectItem><SelectItem value="CN">CN</SelectItem></SelectContent>
            </Select>
          </Labelled>
          <Labelled label="Country">
            <Select name="country" defaultValue={f.country || ANY}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any</SelectItem>
                {[...new Set([...countries, ...(f.country ? [f.country] : [])])].map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}
              </SelectContent>
            </Select>
          </Labelled>
          <Labelled label="Supplier"><Input name="supplier" defaultValue={f.supplier} placeholder="Part of the name" /></Labelled>
          <Labelled label="Factory"><Input name="factory" defaultValue={f.factory} placeholder="Part of the name" /></Labelled>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={clear}>Clear</Button>
            <Button type="submit">Search</Button>
          </div>
        </form>
        {problem && <p className="text-danger" role="alert">{problem}</p>}
      </div>

      {/* dimmed while the figures for new filters load */}
      <div aria-busy={loading} className={cn(scroller, "transition-opacity duration-200", loading && data && "opacity-50")}>
        <Table aria-label="Suppliers">
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">
                <Checkbox aria-label="Select all on this page" checked={allShown} disabled={!shown.length} onCheckedChange={(v) => tickShown(v === true)} />
              </TableHead>
              <TableHead>Supplier</TableHead><TableHead>Region</TableHead><TableHead>Countries</TableHead>
              <TableHead className={R}>Factories</TableHead><TableHead className={R}>Lines</TableHead>
              <TableHead className={R}>Compliance ↑</TableHead><TableHead className={R}>3-month avg</TableHead>
              <TableHead className={R}>vs {prev}</TableHead><TableHead className={R}>Rank</TableHead><TableHead>Report</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.length === 0 && (
              <TableRow>
                <TableCell colSpan={11} className="py-7 text-center text-ink2">
                  {data ? "No lines match these filters." : problem ? "The figures could not be loaded." : "Loading"}
                </TableCell>
              </TableRow>
            )}
            {shown.map((r) => (
              <TableRow key={r.name} data-state={ticked.has(r.name) ? "selected" : undefined}>
                <TableCell><Checkbox aria-label={`Select ${r.name}`} checked={ticked.has(r.name)} onCheckedChange={() => tick(r.name)} /></TableCell>
                <TableCell><SupplierLink name={r.name} month={m} /></TableCell>
                <TableCell>{r.region}</TableCell>
                <TableCell>{r.countries.join(", ")}</TableCell>
                <TableCell className={R}>{int(r.factories)}</TableCell>
                <TableCell className={R}>{int(r.lines)}</TableCell>
                <TableCell className={R}><Rate value={r.compliance} /></TableCell>
                <TableCell className={R}><Rate value={r.avg_3m} /></TableCell>
                <TableCell className={cn(R, r.change != null && (r.change < 0 ? "font-semibold text-danger" : "font-semibold text-ok"))}>
                  {points(r.change).replace(" pts", "")}
                </TableCell>
                <TableCell className={R}>{r.rank ?? "–"}</TableCell>
                <TableCell>
                  <RowFiles name={r.name} month={m} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-line px-4.5 pt-3.5 text-xs text-ink2">
        <span>Page {page} of {pages} · {int(rows.length)} supplier{rows.length === 1 ? "" : "s"}</span>
        {pages > 1 && (
          <nav className="ml-auto flex gap-1" aria-label="Pages">
            {pageList(page, pages).map((p, i) => p == null
              ? <span key={`gap${i}`} className="px-1.5 py-1" aria-hidden="true">…</span>
              : <Button key={p} size="sm" variant={p === page ? "secondary" : "ghost"} aria-current={p === page ? "page" : undefined}
                  aria-label={`Page ${p}`} onClick={() => go({ ...f, page: p })}>{p}</Button>)}
          </nav>
        )}
      </div>

      {/* in a portal on <body>: a transform left on the arriving card would otherwise anchor this fixed bar to the card */}
      {ticked.size > 0 && createPortal(
        <div data-selbar role="toolbar" aria-label="Selected suppliers"
          className="fixed bottom-4.5 left-1/2 z-30 flex w-max max-w-[calc(100%-32px)] -translate-x-1/2 flex-wrap items-center gap-3 rounded-xl bg-surface py-2 pr-2 pl-4 shadow-(--pop)">
          <span aria-live="polite"><b className="font-semibold">{int(ticked.size)}</b> selected</span>
          <Button variant="secondary" onClick={downloadData} disabled={zip.busy}>{zip.busy ? "Preparing…" : "Download data"}</Button>
          <Button onClick={downloadPdfs} disabled={starting || jobRunning}>{starting ? "Starting…" : "Download PDFs"}</Button>
        </div>,
        document.body,
      )}
    </Section>
  );
}

/** One row's PDF and Data buttons; each shows "Preparing…" while its file is made (the PDF renders on demand). */
function RowFiles({ name, month }: { name: string; month: string }) {
  const pdf = useDownload();
  const data = useDownload();
  const link = "h-auto p-0 font-medium text-link hover:underline";
  return (
    <span className="inline-flex gap-2">
      <Button variant="link" className={link} disabled={pdf.busy} aria-label={`PDF report for ${name}`}
        onClick={() => pdf.start(fileUrl("/supplier-pdf", { supplier: name, month }), `${name}_${month}.pdf`)}>
        {pdf.busy ? "Preparing…" : "PDF"}
      </Button>
      <span aria-hidden="true">·</span>
      <Button variant="link" className={link} disabled={data.busy} aria-label={`Data workbook for ${name}`}
        onClick={() => data.start(fileUrl("/supplier-data", { supplier: name, month }), `${name}_${month}.xlsx`)}>
        {data.busy ? "Preparing…" : "Data"}
      </Button>
    </span>
  );
}

function Labelled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1.5 block text-xs font-medium text-ink2">{label}</span>
      {children}
    </label>
  );
}
