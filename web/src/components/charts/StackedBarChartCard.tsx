"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartCard, LABEL, rows, sid, tickValue, tooltip, yDomain, type ChartCardProps } from "./ChartCard";

/** Bars by label (month) with the series stacked; the top one gets the rounded corners. */
export function StackedBarChartCard(props: ChartCardProps) {
  const { labels, series, unit } = props;
  return (
    <ChartCard {...props}>
      <BarChart data={rows(labels, series)} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey={LABEL} tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis width={unit === "%" ? 44 : 56} tickLine={false} axisLine={false} tickFormatter={tickValue(unit)} domain={yDomain(unit)} />
        {tooltip(unit, { fill: "var(--fill)" })}
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={sid(i)} name={sid(i)} stackId="stack" fill={`var(--color-${sid(i)})`} maxBarSize={28}
            isAnimationActive={false} radius={i === series.length - 1 ? [4, 4, 0, 0] : 0} />
        ))}
      </BarChart>
    </ChartCard>
  );
}
