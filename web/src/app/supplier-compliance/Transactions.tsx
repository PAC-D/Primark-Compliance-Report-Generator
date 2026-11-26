"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet } from "@/lib/api";
import { int } from "@/lib/format";
import { cn } from "@/lib/utils";
import { scroller, Section } from "../dashboard/parts";
import type { Transaction, TransactionPage } from "./types";

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** "2026-07-30T06:03:00-07:00" -> "30 Jul 2026", the date as stored (the PDF's strftime("%d %b %Y")). */
const day = (s: string | null) => (s ? `${s.slice(8, 10)} ${MON[Number(s.slice(5, 7)) - 1]} ${s.slice(0, 4)}` : "");
const mm = (v: number | null) => Math.trunc(v ?? 0);
const STATUS: Record<string, string> = { Approved: "text-ok", Pending: "text-warn", Escalated: "text-warn", Compliant: "text-ok" };
const status = (s: string | null) => <span className={cn("font-semibold", (s && STATUS[s]) || "text-danger")}>{s}</span>;

const COLUMNS: [string, (t: Transaction) => React.ReactNode, string?][] = [
  ["Origin", (t) => t.origin_country],
  ["Factory", (t) => t.factory, "font-medium whitespace-normal min-w-44"],
  ["Destination PO", (t) => t.destination_po],
  ["Kimball", (t) => t.kimball],
  ["Size", (t) => t.size, "whitespace-normal min-w-24"],
  ["PO qty", (t) => (t.po_qty == null ? "" : int(t.po_qty)), "text-right"],
  ["Current handover date", (t) => day(t.handover_date)],
  ["Units per carton", (t) => t.units_per_carton, "text-right"],
  ["Outer carton (L×W×H mm)", (t) => `${mm(t.carton_length_mm)}×${mm(t.carton_width_mm)}×${mm(t.carton_height_mm)}`],
  ["Packaging supplier", (t) => t.packaging_supplier, "whitespace-normal min-w-44"],
  ["Updated date", (t) => day(t.updated_date)],
  ["Approved date", (t) => day(t.approved_date)],
  ["Confirmation status", (t) => status(t.packaging_status)],
  ["Compliance status", (t) => status(t.compliance_status)],
];

/** The PDF's transaction pages: 50 lines a page, searched on the server (destination PO, Kimball, factory, description).
 *  Keyed by supplier and month by the caller, so a new supplier starts on page 1 with no search. */
export function Transactions({ supplier, month }: { supplier: string; month: string }) {
  const [q, setQ] = useState("");
  const [text, setText] = useState(""); // q, 250 ms after typing stops
  const [page, setPage] = useState(1);
  const [data, setData] = useState<TransactionPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setText(q.trim()); setPage(1); }, 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setProblem(null);
    apiGet<TransactionPage>("/supplier-transactions", { supplier, month, q: text, page: String(page) })
      .then((d) => live && setData(d), (e) => {
        if (!live) return;
        setData(null);
        setProblem(e instanceof Error ? e.message : String(e));
      })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [supplier, month, text, page]);

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const first = data ? (data.page - 1) * data.page_size : 0;

  return (
    <Section title="Transactions" caption={data ? `${int(data.total)} line${data.total === 1 ? "" : "s"}${text ? ` matching “${text}”` : ""}` : "Loading"}
>
      <div className="px-4.5 pb-3.5">
        <Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="PO, Kimball, factory or description"
          aria-label="Search transactions" className="w-full sm:w-72" />
      </div>
      {problem && <p role="alert" className="px-4.5 pb-3 text-danger">{problem}</p>}
      <div aria-busy={loading} className={cn(scroller, "transition-opacity duration-200", loading && data && "opacity-50")}>
        <Table aria-label="Transactions">
          <TableHeader>
            <TableRow>
              <TableHead className="text-right">#</TableHead>
              {COLUMNS.map(([h, , c]) => <TableHead key={h} className={c?.includes("text-right") ? "text-right" : undefined}>{h}</TableHead>)}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.rows.length === 0 && (
              <TableRow><TableCell colSpan={COLUMNS.length + 1} className="py-7 text-center text-ink2">No lines match.</TableCell></TableRow>
            )}
            {data?.rows.map((t, i) => (
              <TableRow key={first + i}>
                <TableCell className="text-right text-ink2">{first + i + 1}</TableCell>
                {COLUMNS.map(([h, v, c]) => <TableCell key={h} className={c}>{v(t)}</TableCell>)}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-line px-4.5 pt-3.5 text-xs text-ink2">
        <span>Page {data?.page ?? page} of {pages}</span>
        <span className="ml-auto flex gap-2">
          <Button size="sm" variant="secondary" disabled={!data || data.page <= 1 || loading} onClick={() => setPage(data!.page - 1)}>Previous</Button>
          <Button size="sm" variant="secondary" disabled={!data || data.page >= pages || loading} onClick={() => setPage(data!.page + 1)}>Next</Button>
        </span>
      </div>
    </Section>
  );
}
