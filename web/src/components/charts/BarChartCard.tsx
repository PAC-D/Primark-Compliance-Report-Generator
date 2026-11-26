"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartCard, LABEL, rows, sid, tickValue, tooltip, yDomain, type ChartCardProps } from "./ChartCard";

/** Bars by label (month), side by side when there is more than one series. */
export function BarChartCard(props: ChartCardProps) {
  const { labels, series, unit } = props;
  return (
    <ChartCard {...props}>
      <BarChart data={rows(labels, series)} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey={LABEL} tickLine={false} axisLine={false} tickMargin={8} minTickGap={0} />
        <YAxis width={unit === "%" ? 44 : 56} tickLine={false} axisLine={false} tickFormatter={tickValue(unit)} domain={yDomain(unit)} />
        {tooltip(unit, { fill: "var(--fill)" })}
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={sid(i)} name={sid(i)} fill={`var(--color-${sid(i)})`} radius={[4, 4, 0, 0]} maxBarSize={28}
            isAnimationActive={false} />
        ))}
      </BarChart>
    </ChartCard>
  );
}
