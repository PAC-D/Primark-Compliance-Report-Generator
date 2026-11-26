"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { ChartCard, LABEL, rows, sid, tickValue, tooltip, yDomain, type ChartCardProps } from "./ChartCard";

/** Lines by label (month). A null value breaks the line; the "all" series is dotted. */
export function LineChartCard(props: ChartCardProps) {
  const { labels, series, unit, digits } = props;
  return (
    <ChartCard {...props}>
      <LineChart data={rows(labels, series)} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey={LABEL} tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis width={unit === "%" ? 44 : 56} tickLine={false} axisLine={false} tickFormatter={tickValue(unit)} domain={yDomain(unit)} />
        {tooltip(unit, true, digits)}
        {series.map((s, i) => (
          <Line key={s.key} dataKey={sid(i)} name={sid(i)} type="linear" stroke={`var(--color-${sid(i)})`} isAnimationActive={false}
            strokeWidth={s.tone === "all" ? 2.4 : 2} strokeDasharray={s.tone === "all" ? "1 5" : undefined} strokeLinecap="round"
            dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }} connectNulls={false} />
        ))}
      </LineChart>
    </ChartCard>
  );
}
