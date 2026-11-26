"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { BAND_CELL, bandOf, scroller, Section, SupplierLink } from "./parts";
import type { Dashboard } from "./types";

// Heat colours follow the app's bands (below 40% red, 40–70% amber, as format.ts::band), not the workbook's
// conditional formatting (which shades 40–60%), so the grid reads like every other page.
const cell = (v: number | null, key?: string) => {
  const b = bandOf(v);
  return (
    <TableCell key={key} className={cn("text-center", b && BAND_CELL[b], v == null && "text-ink2")}>
      {v == null ? <><span aria-hidden="true">–</span><span className="sr-only">no data</span></> : `${v.toFixed(1)}%`}
    </TableCell>
  );
};

/** The Yearly Performance sheet: every supplier × month, heat-coloured by band, with the average of its months. */
export function Yearly({ d, month }: { d: Dashboard; month: string }) {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const rows = d.all_supplier_trend.map((s, i) => ({ ...s, n: i + 1 })).filter((s) => !needle || s.supplier.toLowerCase().includes(needle));
  return (
    <Section title="Yearly Performance" caption={`Every supplier, January to ${d.month_name} ${d.year} · ${rows.length} of ${d.all_supplier_trend.length}`}
      action={<Input type="search" aria-label="Search suppliers" placeholder="Search suppliers" value={q} onChange={(e) => setQ(e.target.value)}
        className="w-44 sm:w-56" />}>
      <div className={scroller}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-right">#</TableHead>
              <TableHead>Supplier</TableHead>
              {d.month_labels.map((l) => <TableHead key={l} className="text-center">{l}</TableHead>)}
              <TableHead className="text-center">Average</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow><TableCell colSpan={d.month_labels.length + 3} className="py-7 text-center text-ink2">No supplier matches.</TableCell></TableRow>
            )}
            {rows.map((s) => {
              const got = s.rates.filter((r): r is number => r != null);
              const mean = got.length ? got.reduce((a, b) => a + b, 0) / got.length : null; // the workbook's AVERAGE skips empty months
              return (
                <TableRow key={s.supplier}>
                  <TableCell className="text-right text-ink2">{s.n}</TableCell>
                  <TableCell><SupplierLink name={s.supplier} month={month} /></TableCell>
                  {d.month_labels.map((l, i) => cell(s.rates[i] ?? null, l))}
                  {cell(mean)}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </Section>
  );
}
