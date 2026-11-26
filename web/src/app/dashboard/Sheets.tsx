"use client";

import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { int } from "@/lib/format";
import { addMonths, monthName } from "@/lib/query";
import { Rate, scroller, Section, SupplierLink } from "./parts";
import type { Dashboard } from "./types";

const R = "text-right";
const COUNTS = [
  ["dest_po_count", "Destination POs"], ["reflected_lines", "Lines"], ["pending", "Pending"],
  ["approved", "Approved"], ["rejected", "Rejected"], ["escalated", "Escalated"],
] as const;

/** The Visibility sheet: lines by origin country, with a totals row. */
export function Visibility({ d }: { d: Dashboard }) {
  return (
    <Section title="Visibility" caption={`Lines by origin country · ${d.month_name} ${d.year}`}>
      <div className={scroller}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Origin country</TableHead>
              {COUNTS.map(([k, l]) => <TableHead key={k} className={R}>{l}</TableHead>)}
            </TableRow>
          </TableHeader>
          <TableBody>
            {d.line_details.map((r) => (
              <TableRow key={r.country}>
                <TableCell>{r.country}</TableCell>
                {COUNTS.map(([k]) => <TableCell key={k} className={R}>{int(r[k])}</TableCell>)}
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell className="font-semibold">Total</TableCell>
              {COUNTS.map(([k]) => <TableCell key={k} className={`${R} font-semibold`}>{int(d.line_totals[k])}</TableCell>)}
            </TableRow>
          </TableFooter>
        </Table>
      </div>
    </Section>
  );
}

/** The Top Performers sheet: suppliers at 95% or more. */
export function TopPerformers({ d, month }: { d: Dashboard; month: string }) {
  return (
    <Section title="Top Performers" caption={`${int(d.top_suppliers.length)} suppliers at 95% or more · ${d.month_name} ${d.year}`}>
      <div className={scroller}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className={R}>#</TableHead><TableHead>Supplier</TableHead><TableHead>Countries</TableHead>
              <TableHead className={R}>Factories</TableHead><TableHead className={R}>Destination POs</TableHead>
              <TableHead className={R}>Lines</TableHead><TableHead className={R}>Compliance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {d.top_suppliers.length === 0 && (
              <TableRow><TableCell colSpan={7} className="py-7 text-center text-ink2">No supplier reached 95% this month.</TableCell></TableRow>
            )}
            {d.top_suppliers.map((s) => (
              <TableRow key={s.supplier}>
                <TableCell className={`${R} text-ink2`}>{s.sl}</TableCell>
                <TableCell><SupplierLink name={s.supplier} month={month} /></TableCell>
                <TableCell>{s.origin_countries}</TableCell>
                <TableCell className={R}>{int(s.factory_count)}</TableCell>
                <TableCell className={R}>{int(s.dest_po_count)}</TableCell>
                <TableCell className={R}>{int(s.reflected_lines)}</TableCell>
                <TableCell className={R}><Rate value={s.compliance_rate} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Section>
  );
}

/** The Follow-Up Required sheet: below 40% this month and on the 3-month average, with the supplier's emails. */
export function FollowUp({ d, month }: { d: Dashboard; month: string }) {
  const short = (n: number) => monthName(addMonths(month, n), { month: "short" });
  return (
    <Section title="Follow-Up Required" caption={`Below 40% this month and on the 3-month average · ${d.month_name} ${d.year}`}>
      <div className={scroller}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className={R}>#</TableHead><TableHead>Supplier</TableHead><TableHead>Countries</TableHead>
              <TableHead className={R}>Factories</TableHead><TableHead className={R}>Destination POs</TableHead>
              <TableHead className={R}>Quantity</TableHead><TableHead className={R}>Lines</TableHead>
              <TableHead className={R}>{short(0)}</TableHead><TableHead className={R}>{short(-1)}</TableHead>
              <TableHead className={R}>{short(-2)}</TableHead><TableHead className={R}>3-month avg</TableHead>
              <TableHead>Emails</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {d.suppliers_below.length === 0 && (
              <TableRow><TableCell colSpan={12} className="py-7 text-center text-ink2">No supplier needs follow-up this month.</TableCell></TableRow>
            )}
            {d.suppliers_below.map((s) => {
              const emails = (d.email_map[s.supplier.trim().toLowerCase()] ?? "").split(",").map((e) => e.trim()).filter(Boolean);
              return (
                <TableRow key={s.supplier}>
                  <TableCell className={`${R} text-ink2`}>{s.sl}</TableCell>
                  <TableCell><SupplierLink name={s.supplier} month={month} /></TableCell>
                  <TableCell>{s.origin_country}</TableCell>
                  <TableCell className={R}>{int(s.factory_count)}</TableCell>
                  <TableCell className={R}>{int(s.dest_po_count)}</TableCell>
                  <TableCell className={R}>{int(s.qty)}</TableCell>
                  <TableCell className={R}>{int(s.reflected_lines)}</TableCell>
                  <TableCell className={R}><Rate value={s.compliance_rate} /></TableCell>
                  <TableCell className={R}><Rate value={s.prev_1_rate} /></TableCell>
                  <TableCell className={R}><Rate value={s.prev_2_rate} /></TableCell>
                  <TableCell className={R}><Rate value={s.avg_3month} className="font-semibold" /></TableCell>
                  <TableCell className="whitespace-normal">
                    {emails.length ? emails.map((e, i) => (
                      <span key={e}>{i > 0 && ", "}<a className="text-link hover:underline" href={`mailto:${e}`}>{e}</a></span>
                    )) : <span className="text-ink2">–</span>}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </Section>
  );
}
