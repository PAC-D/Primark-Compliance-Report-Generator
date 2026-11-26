"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { addMonths, monthName } from "@/lib/query";

/** The month: the 12 months up to the latest with data (plus the chosen one, if older). */
export function MonthPicker({ latest, value, onChange }: { latest: string | null; value: string | null; onChange: (m: string) => void }) {
  const months = latest ? Array.from({ length: 12 }, (_, i) => addMonths(latest, -i)) : [];
  if (value && !months.includes(value)) months.push(value);
  return (
    <Select value={value ?? undefined} onValueChange={onChange} disabled={!value}>
      <SelectTrigger aria-label="Month" className="w-44"><SelectValue placeholder="Month" /></SelectTrigger>
      <SelectContent>{months.map((m) => <SelectItem key={m} value={m}>{monthName(m)}</SelectItem>)}</SelectContent>
    </Select>
  );
}
