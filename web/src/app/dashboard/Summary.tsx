"use client";

import { BarChartCard } from "@/components/charts/BarChartCard";
import { LineChartCard } from "@/components/charts/LineChartCard";
import { Num, NumberFlowGroup } from "@/components/Num";
import { Card } from "@/components/ui/card";
import { addMonths, monthName } from "@/lib/query";
import type { Dashboard } from "./types";

const avg = (v: (number | null | undefined)[]) => {
  const n = v.filter((x): x is number => x != null);
  return n.length ? n.reduce((a, b) => a + b, 0) / n.length : null;
};

function Stat({ label, caption, children }: { label: string; caption: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card data-arrive className="gap-1.5 px-4.5">
      <div className="text-xs font-medium text-ink2">{label}</div>
      <div className="text-[28px] leading-tight font-bold tracking-[-.022em]">{children}</div>
      <div className="text-xs text-ink2">{caption}</div>
    </Card>
  );
}

/** The workbook's Summary sheet: the tiles, compliance by country this month and the country trend. */
export function Summary({ d, month }: { d: Dashboard; month: string }) {
  // "Average compliance" is the workbook's tile exactly: the plain average of this month's country scores
  // (summary_excel.py, SUBTOTAL(101) over the Compliance Rate by Country table). The workbook has no change; ours
  // compares like with like: the countries with a rate in both this month and last (the trend's last two columns),
  // so a country appearing or vanishing doesn't move it. None in January, as the trend starts there.
  const n = d.chart_labels.length;
  const now = avg(d.compliance_data.map((c) => c.compliance_rate));
  const both = n > 1
    ? d.country_order.map((c) => d.country_data[c] ?? []).filter((r) => r[n - 1] != null && r[n - 2] != null)
    : [];
  const change = both.length ? avg(both.map((r) => r[n - 1]))! - avg(both.map((r) => r[n - 2]))! : null;
  const prev = monthName(addMonths(month, -1), { month: "long" });

  return (
    <>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3.5">
        <Stat label="Suppliers" caption="Sources this month"><Num value={d.sources.total_suppliers} /></Stat>
        <Stat label="Factories" caption="Sources this month"><Num value={d.sources.total_factories} /></Stat>
        <Stat label="Lines" caption="Reflected lines"><Num value={d.line_totals.reflected_lines} /></Stat>
        <NumberFlowGroup>
          <Stat label="Average compliance" caption={change == null ? "Across countries" : (
            <><span className={change < 0 ? "font-semibold text-danger" : "font-semibold text-ok"}>
              <Num value={change} format={{ minimumFractionDigits: 1, maximumFractionDigits: 1 }} suffix=" pts" signed />
            </span> vs {prev}</>
          )}>
            <Num value={now} format={{ minimumFractionDigits: 1, maximumFractionDigits: 1 }} suffix="%" />
          </Stat>
        </NumberFlowGroup>
        <Stat label="Working days" caption="Monday to Friday"><Num value={d.working_days} /></Stat>
        <Stat label="Calendar days" caption={`In ${d.month_name}`}><Num value={d.days_in_month} /></Stat>
      </div>
      <div data-arrive className="grid gap-3.5 lg:grid-cols-2">
        <BarChartCard title="Compliance by country" subtitle={`${d.month_name} ${d.year}`} unit="%"
          labels={d.compliance_data.map((c) => c.country)}
          series={[{ key: "rate", label: "Compliance", values: d.compliance_data.map((c) => c.compliance_rate), tone: "chart-1" }]} />
        <LineChartCard title="Compliance by country, by month" unit="%"
          subtitle={n ? `${d.chart_labels[0]} to ${d.chart_labels[n - 1]} · a gap where a country shipped nothing` : undefined}
          labels={d.chart_labels}
          series={d.country_order.map((c, i) => ({ key: c, label: c, values: d.country_data[c] ?? [], tone: `chart-${(i % 9) + 1}` as const }))} />
      </div>
    </>
  );
}
