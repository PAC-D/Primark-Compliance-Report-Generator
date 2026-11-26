"use client";

import type { ReactNode } from "react";
import { BarChartCard } from "@/components/charts/BarChartCard";
import { LineChartCard } from "@/components/charts/LineChartCard";
import { Num, NumberFlowGroup } from "@/components/Num";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { int } from "@/lib/format";
import { cn } from "@/lib/utils";
import { BAND_TEXT, Rate, scroller, Section } from "../dashboard/parts";
import type { BandKey, SupplierReport } from "./types";

const R = "text-right";
const BANDS: { key: BandKey; label: string; tone: "hi" | "mid" | "lo"; bg: string }[] = [
  { key: "high", label: "70%+", tone: "hi", bg: "bg-ok" },
  { key: "mid", label: "40–70%", tone: "mid", bg: "bg-warn" },
  { key: "low", label: "Below 40%", tone: "lo", bg: "bg-danger" },
];
const toneOf = (b: BandKey) => BANDS.find((x) => x.key === b)!;
const RATE_DP = { minimumFractionDigits: 1, maximumFractionDigits: 2 }; // as the PDF prints it: 54.89%, 100.0%

function Shared() {
  return <Badge className="bg-warn-soft text-warn">Shared</Badge>;
}

function Tile({ label, aside, children }: { label: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <Card data-arrive className="gap-2 px-4.5">
      <div className="flex items-center justify-between gap-2 text-xs font-medium text-ink2"><span>{label}</span>{aside && <span>{aside}</span>}</div>
      {children}
    </Card>
  );
}

/** The supplier PDF on screen, in its order: hero, cards, charts, then the factory tables. */
export function Report({ d }: { d: SupplierReport }) {
  const countries = (d.kpis.origin_country || "").split(", ").filter(Boolean);
  const tone = toneOf(d.band);
  const fb = (b: BandKey) => d.factory_bands[b] ?? 0;
  const period = `${d.month_name} ${d.year}`;
  const labelsSpan = (l: string[]) => (l.length ? `${l[0]} to ${l[l.length - 1]}` : undefined);

  return (
    <>
      {/* Hero */}
      <div data-arrive className="flex flex-wrap items-center gap-x-6 gap-y-4 rounded-2xl bg-primary px-6 py-5 text-white">
        <div className="min-w-0 flex-1 basis-64">
          <div className="text-xs font-medium text-white/70">Supplier</div>
          <h2 className="mt-0.5 text-[22px] leading-tight font-bold tracking-[-.015em] break-words">{d.supplier_name}</h2>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {countries.map((c) => <span key={c} className="rounded-full bg-white/15 px-2.5 py-0.5 text-xs">{c}</span>)}
            <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-xs">
              {int(d.kpis.factory_count)} factor{d.kpis.factory_count === 1 ? "y" : "ies"}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs font-medium text-white/70">Overall rank</div>
          <div className="text-[44px] leading-none font-bold tracking-[-.03em]">#<Num value={d.ranking} /></div>
          <div className="mt-1 text-xs text-white/80">of {int(d.total_suppliers)} suppliers</div>
          {d.shared && <div className="mt-1.5"><Shared /></div>}
        </div>
      </div>

      {/* Cards */}
      <div className="grid gap-3.5 md:grid-cols-[1fr_.8fr_1.2fr]">
        <Tile label="Compliance rate" aside={<span className={cn("font-semibold", BAND_TEXT[tone.tone])}>{tone.label}</span>}>
          <NumberFlowGroup>
            <div className={cn("text-[28px] leading-tight font-bold tracking-[-.022em]", BAND_TEXT[tone.tone])}>
              <Num value={d.compliance_rate} format={RATE_DP} suffix="%" />
            </div>
          </NumberFlowGroup>
          <div className="h-1.5 overflow-hidden rounded-full bg-fill">
            <i className={cn("block h-full rounded-full", tone.bg)} style={{ width: `${Math.min(100, d.compliance_rate)}%` }} />
          </div>
          <div className="flex justify-between text-xs text-ink2">
            <span><b className="font-semibold text-ink">{int(d.kpis.compliant_count)}</b> compliant lines</span>
            <span><b className="font-semibold text-ink">{int(d.kpis.total_lines)}</b> total</span>
          </div>
        </Tile>
        <Tile label="Factories" aside="This month">
          <div className="text-[28px] leading-tight font-bold tracking-[-.022em]"><Num value={d.kpis.factory_count} /></div>
          <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-fill">
            {BANDS.filter((b) => fb(b.key)).map((b) => <i key={b.key} className={cn("block h-full", b.bg)} style={{ flex: fb(b.key) }} />)}
          </div>
          <div className="flex flex-wrap justify-between gap-x-3 text-xs text-ink2">
            {BANDS.map((b) => (
              <span key={b.key}><b className={cn("font-semibold", BAND_TEXT[b.tone])}>{fb(b.key)}</b> {b.label}</span>
            ))}
          </div>
        </Tile>
        <Tile label="Rank per country">
          <ul className="flex flex-col">
            {d.local_rankings.map((l) => (
              <li key={l.country} className="flex items-center justify-between gap-2 border-t border-line2 py-1.5 first:border-t-0">
                <span>{l.country}</span>
                <span className="flex items-center gap-2">
                  {l.shared && <Shared />}
                  <span><b className="text-base font-semibold">#{l.rank}</b> <small className="text-ink2">of {int(l.total)}</small></span>
                </span>
              </li>
            ))}
          </ul>
        </Tile>
      </div>

      {/* Charts */}
      <div data-arrive className="grid gap-3.5 lg:grid-cols-3">
        <BarChartCard title="Monthly compliance" subtitle={labelsSpan(d.monthly_compliance_labels)} unit="%" labels={d.monthly_compliance_labels}
          series={[{ key: "rate", label: "Compliance", values: d.monthly_compliance_scores, tone: "chart-1" }]} />
        <BarChartCard title="Standard carton usage" subtitle={labelsSpan(d.standard_carton_labels)} unit="%" labels={d.standard_carton_labels}
          series={[{ key: "std", label: "Standard cartons", values: d.standard_carton_scores, tone: "chart-2" }]} />
        <LineChartCard title="Product density" subtitle="Units per CBM" unit="count" digits={0} labels={d.density_labels}
          series={[{ key: "density", label: "Units per CBM", values: d.density_scores, tone: "chart-2" }]} />
      </div>

      {/* Tables */}
      <Section title="Associated factories" caption={period}>
        <div className={scroller}>
          <Table>
            <TableHeader>
              <TableRow><TableHead className={R}>#</TableHead><TableHead>Factory</TableHead><TableHead>Origin country</TableHead>
                <TableHead className={R}>Compliance</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {d.associated_factories.map((f, i) => (
                <TableRow key={f.factory}>
                  <TableCell className={cn(R, "text-ink2")}>{i + 1}</TableCell>
                  <TableCell className="font-medium">{f.factory}</TableCell>
                  <TableCell>{f.origin_countries}</TableCell>
                  <TableCell className={R}><Rate value={f.compliance_rate} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Section>

      <Section title="Line details" caption={`By factory · ${period}`}>
        <div className={scroller}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Factory</TableHead><TableHead className={R}>Destination POs</TableHead><TableHead className={R}>Reflected lines</TableHead>
                <TableHead className={R}>Pending</TableHead><TableHead className={R}>Approved</TableHead>
                <TableHead className={R}>Rejected</TableHead><TableHead className={R}>Escalated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.line_details.map((f) => (
                <TableRow key={f.factory}>
                  <TableCell className="font-medium">{f.factory}</TableCell>
                  <TableCell className={R}>{int(f.dest_po_count)}</TableCell>
                  <TableCell className={R}>{int(f.reflected_lines)}</TableCell>
                  <TableCell className={cn(R, "text-warn")}>{int(f.pending)}</TableCell>
                  <TableCell className={cn(R, "text-ok")}>{int(f.approved)}</TableCell>
                  <TableCell className={cn(R, "text-danger")}>{int(f.rejected)}</TableCell>
                  <TableCell className={R}>{int(f.escalated)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow className="font-semibold">
                <TableCell>Total</TableCell>
                <TableCell className={R}>{int(d.line_totals.dest_po_count)}</TableCell>
                <TableCell className={R}>{int(d.line_totals.reflected_lines)}</TableCell>
                <TableCell className={R}>{int(d.line_totals.pending)}</TableCell>
                <TableCell className={R}>{int(d.line_totals.approved)}</TableCell>
                <TableCell className={R}>{int(d.line_totals.rejected)}</TableCell>
                <TableCell className={R}>{int(d.line_totals.escalated)}</TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </div>
      </Section>

      <Section title="Standard carton usage" caption={`And corrugated board consumption · ${period}`}>
        <div className={scroller}>
          <Table>
            <TableHeader>
              <TableRow><TableHead>Factory</TableHead><TableHead className={R}>Standard carton usage</TableHead>
                <TableHead className={R}>Corrugated board (m²)</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {d.compliance_data.map((f) => (
                <TableRow key={f.factory}>
                  <TableCell className="font-medium">{f.factory}</TableCell>
                  <TableCell className={R}>{f.standard_carton_pct.toFixed(1)}%</TableCell>
                  <TableCell className={R}>{f.corrugated_sqm.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} m²</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Section>
    </>
  );
}
