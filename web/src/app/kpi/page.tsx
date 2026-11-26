"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { LineChartCard } from "@/components/charts/LineChartCard";
import { StackedBarChartCard } from "@/components/charts/StackedBarChartCard";
import { JobStatus, startJob, type Job } from "@/components/JobStatus";
import { MonthPicker } from "@/components/MonthPicker";
import { Num, NumberFlowGroup } from "@/components/Num";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiGet, outputUrl } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { int } from "@/lib/format";
import { useArrival } from "@/lib/motion";
import { addMonths, monthName, readFilters, writeFilters, type Filters } from "@/lib/query";
import { cn } from "@/lib/utils";
import { Section, scroller } from "../dashboard/parts";

/** GET /api/kpi (tps/metrics/dashboard.py::kpi). */
type Working = { lines: number; working_days: number; avg: number };
type People = { suppliers: number[]; factories: number[] };
type Country = { country: string; region: "BD" | "CN"; cells: (number | null)[]; share: number };
type Approver = { name: string; lines: [number, number]; change_pct: number | null };
type Data = {
  month: string;
  cards: {
    lines: number; lines_change_pct: number | null; suppliers: number; suppliers_change: number | null;
    factories: number; factories_change: number | null; bd: Working; cn: Working;
  };
  region_lines: { labels: string[]; bd: number[]; cn: number[] };
  people: { labels: string[]; bd: People; cn: People };
  table_months: string[];
  countries: Country[];
  approvers: Approver[];
};

const KPI_JOB = "KPI Report"; // api/routes.py JOBS["kpi"]; the job is named "KPI Report · August 2026"
const ANY = "any"; // a Select item can't have "" as its value
const REGIONS = ["all", "BD", "CN"] as const;
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const tone = (v: number) => (v < 0 ? "text-danger" : "text-ok");

function Stat({ label, caption, children }: { label: string; caption?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card data-arrive className="gap-1.5 px-4.5">
      <div className="text-xs font-medium text-ink2">{label}</div>
      <div className="text-[28px] leading-tight font-bold tracking-[-.022em]">{children}</div>
      <div className="min-h-4 text-xs text-ink2">{caption}</div>
    </Card>
  );
}

/** A change since last month, rolling with its figure; absent (null) shows nothing. */
function Change({ value, percent, prev }: { value: number | null | undefined; percent?: boolean; prev: string }) {
  if (value == null) return null;
  return (
    <>
      <span className={cn("font-semibold", value !== 0 && tone(value))}>
        <Num value={value} signed suffix={percent ? "%" : undefined} />
      </span> vs {prev}
    </>
  );
}

function Filter({ label, value, any, options, onChange }: {
  label: string; value: string; any: string; options: string[]; onChange: (v: string) => void;
}) {
  return (
    <label className="block min-w-0">
      <span className="mb-1.5 block text-xs font-medium text-ink2">{label}</span>
      <Select value={value || ANY} onValueChange={(v) => onChange(v === ANY ? "" : v)}>
        <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>{any}</SelectItem>
          {[...new Set([...options, ...(value ? [value] : [])])].map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}
        </SelectContent>
      </Select>
    </label>
  );
}

function Kpi() {
  const router = useRouter();
  const path = usePathname();
  const search = useSearchParams();
  const f = useMemo(() => readFilters(new URLSearchParams(search.toString())), [search]);
  const go = (next: Filters) => router.push(`${path}?${writeFilters(next)}`, { scroll: false });

  const [latest, setLatest] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<{ month: string; d: Data } | null>(null); // labels come from the loaded month
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<string | null>(null);
  const [opts, setOpts] = useState<{ countries: string[]; approvers: string[] }>({ countries: [], approvers: [] });
  const [jobProblem, setJobProblem] = useState<string | null>(null);
  const [jobRunning, setJobRunning] = useState(false);
  const [preparing, setPreparing] = useState(false); // our KPI job is running, then its file downloading
  const month = f.month || latest;
  const scope = useRef<HTMLElement>(null);
  useArrival(scope, [!!loaded]);

  useEffect(() => {
    apiGet<{ month: string }>("/latest-month").then((r) => setLatest(r.month), (e) => setProblem(message(e)));
  }, []);

  useEffect(() => {
    if (!month) return;
    let live = true;
    apiGet<typeof opts>("/options", { month })
      .then((o) => live && setOpts(o), (e) => live && setProblem(message(e)));
    return () => { live = false; };
  }, [month]);

  useEffect(() => {
    if (!month) return;
    let live = true;
    setProblem(null);
    setLoading(true);
    apiGet<Data>("/kpi", { month, region: f.region, country: f.country, approved_by: f.approved_by })
      .then((d) => live && setLoaded({ month, d }), (e) => {
        if (!live) return;
        setLoaded(null); // never leave the last filter's figures under an error
        setProblem(message(e));
      })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [month, f.region, f.country, f.approved_by]);

  const downloadReport = async () => {
    if (!month || preparing) return;
    setPreparing(true);
    setJobProblem(null);
    const body = new FormData();
    body.set("month", month);
    const refused = await startJob("/jobs/kpi", body);
    if (refused) {
      setJobProblem(refused);
      setPreparing(false);
    }
  };
  // onFinish fires for any job this page sees finish; only ours (a KPI job while preparing) downloads
  const finished = async (job: Job) => {
    if (!preparing || !job.name.startsWith(KPI_JOB)) return;
    const file = job.state === "done" ? job.result?.files[0] : undefined;
    if (file) {
      const name = file.slice(file.lastIndexOf("/") + 1);
      try {
        await downloadFile(outputUrl(file), name);
        toast.success("Downloaded", { description: name });
      } catch (e) {
        toast.error("Download failed", { description: message(e) });
      }
    }
    setPreparing(false);
  };

  const m = loaded?.month ?? month; // labels follow the figures on screen, not a month still loading
  const d = loaded?.d;
  const c = d?.cards;
  const prevName = m ? monthName(addMonths(m, -1), { month: "long" }) : "last month";
  const empty = c != null && c.lines === 0;
  const labels = d?.region_lines.labels ?? [];
  const caption = labels.length > 1 ? `${labels[0]} to ${labels.at(-1)}` : undefined;
  const showBd = f.region !== "CN", showCn = f.region !== "BD";
  const bdcn = (get: (r: "bd" | "cn") => number[], key: string) => [
    ...(showBd ? [{ key: `${key}-bd`, label: "BD", values: get("bd"), tone: "bd" as const }] : []),
    ...(showCn ? [{ key: `${key}-cn`, label: "CN", values: get("cn"), tone: "cn" as const }] : []),
  ];

  const [now, prev, last] = d?.table_months ?? ["", "", ""];
  const R = "text-right";
  const none = d ? "No lines match these filters." : problem ? "The figures could not be loaded." : "Loading";

  return (
    <section ref={scope} className="flex flex-col gap-3.5">
      <div data-arrive className="head">
        <div>
          <h1>KPI Dashboard</h1>
          <p>{m ? `${monthName(m)} · compared with ${prevName} and ${monthName(addMonths(m, -12))}` : "Loading"}</p>
        </div>
        <div className="act">
          <Tabs value={f.region || "all"} onValueChange={(r) => go({ ...f, region: r === "all" ? "" : r })}>
            <TabsList aria-label="Region">
              {REGIONS.map((r) => <TabsTrigger key={r} value={r}>{r === "all" ? "All regions" : r}</TabsTrigger>)}
            </TabsList>
          </Tabs>
          <Button onClick={downloadReport} disabled={!month || preparing || jobRunning}>
            {preparing ? "Preparing…" : "Download KPI report"}
          </Button>
        </div>
      </div>

      <div data-arrive className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] items-end gap-x-3.5 gap-y-3">
        <label className="block min-w-0">
          <span className="mb-1.5 block text-xs font-medium text-ink2">Month</span>
          <MonthPicker latest={latest} value={month} onChange={(v) => go({ ...f, month: v })} />
        </label>
        <Filter label="Country" value={f.country} any="Any" options={opts.countries} onChange={(v) => go({ ...f, country: v })} />
        <Filter label="Approved by" value={f.approved_by} any="Anyone" options={opts.approvers} onChange={(v) => go({ ...f, approved_by: v })} />
        <div className="flex justify-end">
          <Button variant="secondary" onClick={() => go({ ...readFilters(new URLSearchParams()), month: f.month })}>Clear</Button>
        </div>
      </div>

      <p className="note">Download KPI report covers the whole month; the region, country and approver filters do not apply to it.</p>
      {problem && <p className="text-danger" role="alert">{problem}</p>}
      {jobProblem && <p className="text-danger" role="alert">{jobProblem}</p>}
      <JobStatus onFinish={finished} onUpdate={(j) => setJobRunning(j?.state === "running")} />

      {/* the old figures stay, dimmed, while new filters load; then the numbers roll */}
      <div aria-busy={loading} className={cn("flex flex-col gap-3.5 transition-opacity duration-200", loading && d && "opacity-50")}>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3.5">
          <NumberFlowGroup>
            <Stat label="Reflected lines" caption={c && <Change value={c.lines_change_pct} percent prev={prevName} />}>
              {c ? <Num value={c.lines} /> : "–"}
            </Stat>
          </NumberFlowGroup>
          <NumberFlowGroup>
            <Stat label="Suppliers" caption={c && <Change value={c.suppliers_change} prev={prevName} />}>
              {c ? <Num value={c.suppliers} /> : "–"}
            </Stat>
          </NumberFlowGroup>
          <NumberFlowGroup>
            <Stat label="Factories" caption={c && <Change value={c.factories_change} prev={prevName} />}>
              {c ? <Num value={c.factories} /> : "–"}
            </Stat>
          </NumberFlowGroup>
          <Stat label="BD lines per working day" caption={c && `${c.bd.working_days} working days, Sunday to Thursday`}>
            {c ? <Num value={c.bd.avg} format={{ maximumFractionDigits: 0 }} /> : "–"}
          </Stat>
          <Stat label="CN lines per working day" caption={c && `${c.cn.working_days} working days, Monday to Friday`}>
            {c ? <Num value={c.cn.avg} format={{ maximumFractionDigits: 0 }} /> : "–"}
          </Stat>
        </div>

        {d && (empty ? <p className="text-ink2">No lines match these filters.</p> : (
          <div data-arrive className="grid gap-3.5 lg:grid-cols-2">
            <StackedBarChartCard title="Reflected lines by region" subtitle={caption} unit="count" labels={labels}
              series={bdcn((r) => d.region_lines[r], "lines")} />
            <div className="flex flex-col gap-3.5">
              <LineChartCard title="Suppliers by month" subtitle={caption} unit="count" labels={d.people.labels}
                series={bdcn((r) => d.people[r].suppliers, "suppliers")} />
              <LineChartCard title="Factories by month" subtitle={caption} unit="count" labels={d.people.labels}
                series={bdcn((r) => d.people[r].factories, "factories")} />
            </div>
          </div>
        ))}

        <div className="grid gap-3.5 lg:grid-cols-2">
          <Section title="Lines by country" caption={m ? monthName(m) : undefined}>
            <div className={scroller}>
              <Table aria-label="Lines by country">
                <TableHeader>
                  <TableRow>
                    <TableHead>Country</TableHead><TableHead>Region</TableHead>
                    {[now, prev, last].map((l, i) => <TableHead key={i} className={R}>{l || "–"}</TableHead>)}
                    <TableHead className={R}>Share</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(d?.countries.length ?? 0) === 0 && (
                    <TableRow><TableCell colSpan={6} className="py-7 text-center text-ink2">{none}</TableCell></TableRow>
                  )}
                  {d?.countries.map((r) => (
                    <TableRow key={r.country}>
                      <TableCell>{r.country}</TableCell>
                      <TableCell>{r.region}</TableCell>
                      {[0, 1, 2].map((i) => (
                        <TableCell key={i} className={R}>{r.cells[i] == null ? <span className="text-ink2">No data</span> : int(r.cells[i]!)}</TableCell>
                      ))}
                      <TableCell className={R}>{r.share}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Section>
          <Section title="Lines by approver" caption={m ? monthName(m) : undefined}>
            <div className={scroller}>
              <Table aria-label="Lines by approver">
                <TableHeader>
                  <TableRow>
                    <TableHead>Approved by</TableHead>
                    <TableHead className={R}>{now || "–"}</TableHead><TableHead className={R}>{prev || "–"}</TableHead><TableHead className={R}>Change</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(d?.approvers.length ?? 0) === 0 && (
                    <TableRow><TableCell colSpan={4} className="py-7 text-center text-ink2">{none}</TableCell></TableRow>
                  )}
                  {d?.approvers.map((r) => (
                    <TableRow key={r.name}>
                      <TableCell>{r.name}</TableCell>
                      <TableCell className={R}>{int(r.lines[0])}</TableCell>
                      <TableCell className={R}>{int(r.lines[1])}</TableCell>
                      <TableCell className={cn(R, r.change_pct != null && r.change_pct !== 0 && cn("font-semibold", tone(r.change_pct)))}>
                        {r.change_pct == null ? "–" : `${r.change_pct < 0 ? "−" : r.change_pct > 0 ? "+" : ""}${int(Math.abs(r.change_pct))}%`}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Section>
        </div>
        <p className="note">Same month last year shows &quot;No data&quot; until a year of files is loaded.</p>
      </div>
    </section>
  );
}

export default function Page() {
  return <Suspense><Kpi /></Suspense>;
}
