"use client";

import { useRef, type CSSProperties, type ReactNode } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { int, pct } from "@/lib/format";
import { useChartDraw } from "@/lib/motion";

/** BD = navy, CN = Primark blue, all = secondary ink (dotted on a line), or any --chart-n. */
export type Tone = "bd" | "cn" | "all" | `chart-${number}`;
export type ChartSeries = { key: string; label: string; values: (number | null)[]; tone: Tone };
export type ChartCardProps = { title: string; subtitle?: string; labels: string[]; series: ChartSeries[]; unit: "%" | "count"; digits?: number }; // digits: most decimals a count shows in the tooltip (default 3, as int)

const TONE: Record<string, string> = { bd: "var(--chart-1)", cn: "var(--chart-2)", all: "var(--chart-3)" };
const toneColor = (t: Tone): string => TONE[t] ?? `var(--${t})`;
export const LABEL = "__label"; // the row's x value; a key no series uses
/** A series' id in the chart config and CSS (--color-s0, …): by position, so any key (spaces, "&", …) is safe in CSS. */
export const sid = (i: number): string => `s${i}`;

/** Recharts rows: one per label, with each series' value under its id (sid), so a key with dots or spaces is safe. */
export const rows = (labels: string[], series: ChartSeries[]) =>
  labels.map((label, i) => Object.fromEntries([[LABEL, label], ...series.map((s, j) => [sid(j), s.values[i] ?? null])]));

const formatValue = (unit: ChartCardProps["unit"], digits?: number) => (v: number | null) =>
  unit === "%" ? pct(v) : v == null ? "–" : digits == null ? int(v) : v.toLocaleString("en-GB", { maximumFractionDigits: digits });
export const tickValue = (unit: ChartCardProps["unit"]) => (v: number) => (unit === "%" ? `${v}%` : int(v));
export const yDomain = (unit: ChartCardProps["unit"]): [number, number | "auto"] => (unit === "%" ? [0, 100] : [0, "auto"]);

/** The hover tooltip: the label, then each series' value with its unit. */
export const tooltip = (unit: ChartCardProps["unit"], cursor: boolean | object = true, digits?: number) => (
  <ChartTooltip cursor={cursor} content={<ChartTooltipContent valueFormatter={formatValue(unit, digits)} />} />
);

/** The card around every chart: title, legend, subtitle, the chart with its hover tooltip, and the draw-in on first view.
 *  Recharts' own animation is off in the charts (isAnimationActive={false}): GSAP draws them in. */
export function ChartCard({ title, subtitle, series, children }: Omit<ChartCardProps, "labels" | "unit"> & {
  children: React.ComponentProps<typeof ChartContainer>["children"];
}) {
  const scope = useRef<HTMLDivElement>(null);
  useChartDraw(scope);
  const config: ChartConfig = Object.fromEntries(series.map((s, i) => [sid(i), { label: s.label, color: toneColor(s.tone) }]));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-baseline gap-x-2.5">
          {title}
          {series.length > 1 && <Legend series={series} />}
        </CardTitle>
        {subtitle && <CardDescription>{subtitle}</CardDescription>}
      </CardHeader>
      <CardContent>
        <ChartContainer ref={scope} config={config} className="aspect-auto h-[220px] w-full">
          {children}
        </ChartContainer>
      </CardContent>
    </Card>
  );
}

function Legend({ series }: { series: ChartSeries[] }): ReactNode {
  return (
    <span className="legend m-0! ml-auto!">
      {series.map((s) => (
        <span key={s.key} className={s.tone === "all" ? "dash" : undefined} style={{ "--c": toneColor(s.tone) } as CSSProperties}>
          {s.label}
        </span>
      ))}
    </span>
  );
}
