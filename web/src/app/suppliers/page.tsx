"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { JobStatus, startJob, type Job } from "@/components/JobStatus";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, apiPost, errorText, fileUrl } from "@/lib/api";
import { useDownload } from "@/lib/download";
import { useArrival } from "@/lib/motion";
import { monthName } from "@/lib/query";
import { cn } from "@/lib/utils";
import { scroller, Section } from "../dashboard/parts";

type Supplier = { name: string; emails: string; region: string | null; months: Record<string, string | null> };

const ANY = "any"; // a Select item can't have "" as its value
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The email box: saves on blur or Enter, only when the text changed. */
function EmailCell({ supplier, onSaved }: { supplier: Supplier; onSaved: (name: string, emails: string) => void }) {
  const [value, setValue] = useState(supplier.emails);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false); // the box is disabled meanwhile, so nothing typed is lost and saves cannot overlap
  const saved = useRef(supplier.emails);
  useEffect(() => {
    setValue((v) => (v === saved.current ? supplier.emails : v)); // a reload never overwrites text being typed
    saved.current = supplier.emails;
  }, [supplier.emails]);

  const save = async () => {
    if (saving || value === saved.current) return;
    setSaving(true);
    try {
      const res = await apiPost("/suppliers/emails", new URLSearchParams({ supplier: supplier.name, emails: value }));
      if (!res.ok) throw new Error(await errorText(res));
      const { emails } = (await res.json()) as { emails: string };
      saved.current = emails;
      setValue(emails);
      setError(null);
      onSaved(supplier.name, emails);
    } catch (e) {
      setError(message(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-w-70">
      <Input value={value} aria-label={`Emails for ${supplier.name}`} aria-invalid={error ? true : undefined}
        disabled={saving} onChange={(e) => setValue(e.target.value)} onBlur={save}
        onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }} />
      {error && <span className="mt-1 block whitespace-normal text-danger" role="alert">{error}</span>}
    </div>
  );
}

export default function Page() {
  const [all, setAll] = useState<Supplier[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const startingNow = useRef(false);
  const [jobRunning, setJobRunning] = useState(false);
  const [q, setQ] = useState("");
  const [region, setRegion] = useState("");
  const [month, setMonth] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const exp = useDownload();
  const scope = useRef<HTMLElement>(null);
  useArrival(scope, [!!all]);

  const [loading, setLoading] = useState(true);
  const seq = useRef(0); // only the latest load may write
  const load = (j?: Job) => {
    if (j?.state === "done") toast.success(j.name, { description: j.result?.summary });
    else if (j?.state === "failed") toast.error(j.name, { description: j.error || "The job failed." });
    const mine = ++seq.current;
    setLoading(true);
    apiGet<Supplier[]>("/suppliers")
      .then((s) => { if (mine === seq.current) { setAll(s); setProblem(null); } },
        (e) => { if (mine === seq.current) { setAll(null); setProblem(message(e)); } })
      .finally(() => { if (mine === seq.current) setLoading(false); });
  };
  useEffect(() => load(), []);

  const months = useMemo(() => [...new Set((all ?? []).flatMap((s) => Object.keys(s.months)))].sort().reverse(), [all]);
  const rows = useMemo(() => (all ?? []).filter((s) => {
    if (q && !s.name.toLowerCase().includes(q.toLowerCase())) return false;
    if (month) return month in s.months && (!region || s.months[month] === region);
    return !region || s.region === region;
  }), [all, q, region, month]);

  const imported = async (f: File | undefined) => {
    if (!f || startingNow.current) return;
    startingNow.current = true;
    setStarting(true);
    const body = new FormData();
    body.set("file", f);
    const refused = await startJob("/suppliers/import", body);
    if (refused) toast.error("Could not start", { description: refused });
    setStarting(false);
    startingNow.current = false;
  };
  const pick = (f: File | undefined) => {
    imported(f);
    if (file.current) file.current.value = ""; // so the same file can be chosen again
  };

  const saved = (name: string, emails: string) => setAll((a) => a && a.map((s) => (s.name === name ? { ...s, emails } : s)));
  const busy = starting || jobRunning;
  const label = "text-xs font-medium text-ink2";

  return (
    <section ref={scope} className="flex flex-col gap-3.5">
      <div className="head">
        <div>
          <h1>Suppliers</h1>
          <p>{all ? `${rows.length} of ${all.length} suppliers` : "Loading"}</p>
        </div>
        <div className="act">
          <input ref={file} type="file" accept=".xlsx" hidden aria-label="Supplier emails file" onChange={(e) => pick(e.target.files?.[0])} />
          <Button variant="secondary" onClick={() => file.current?.click()} disabled={busy}>Import</Button>
          <Button variant="secondary" disabled={exp.busy} onClick={() => exp.start(fileUrl("/suppliers/export"), "Supplier_Emails.xlsx")}>
            {exp.busy ? "Preparing…" : "Export"}
          </Button>
        </div>
      </div>

      <div data-arrive className="grid grid-cols-[repeat(auto-fill,minmax(190px,1fr))] items-end gap-x-3.5 gap-y-3">
        <label className="flex flex-col gap-1.5"><span className={label}>Search</span>
          <Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Supplier name" />
        </label>
        <div className="flex flex-col gap-1.5"><span className={label} id="f-region">Region</span>
          <Select value={region || ANY} onValueChange={(v) => setRegion(v === ANY ? "" : v)}>
            <SelectTrigger aria-labelledby="f-region" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value={ANY}>Any</SelectItem><SelectItem value="BD_Region">BD</SelectItem><SelectItem value="CN_Region">CN</SelectItem></SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1.5"><span className={label} id="f-month">Month with data</span>
          <Select value={month || ANY} onValueChange={(v) => setMonth(v === ANY ? "" : v)}>
            <SelectTrigger aria-labelledby="f-month" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any</SelectItem>
              {months.map((m) => <SelectItem key={m} value={m}>{monthName(m)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {problem && <p className="text-danger" role="alert">{problem}</p>}
      <JobStatus onUpdate={(j: Job | null) => setJobRunning(j?.state === "running")} onFinish={load} />
      <Section title="Suppliers" caption="Emails save when you leave the box or press Enter. Separate addresses with commas or semicolons.">
        <div aria-busy={loading} className={cn(scroller, "transition-opacity duration-200", loading && all && "opacity-50")}>
          <Table>
            <TableHeader><TableRow><TableHead>Supplier</TableHead><TableHead>Region</TableHead><TableHead>Emails</TableHead></TableRow></TableHeader>
            <TableBody>
              {rows.length === 0 && (
                <TableRow><TableCell colSpan={3} className="py-7 text-center text-ink2">
                  {all ? "No suppliers match these filters." : problem ? "The suppliers could not be loaded." : "Loading"}
                </TableCell></TableRow>
              )}
              {rows.map((s) => (
                <TableRow key={s.name}>
                  <TableCell>{s.name}</TableCell>
                  <TableCell>{s.region ?? <span className="text-ink2">No data</span>}</TableCell>
                  <TableCell><EmailCell supplier={s} onSaved={saved} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Section>
    </section>
  );
}
