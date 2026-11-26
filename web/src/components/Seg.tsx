"use client";

import type { ReactNode } from "react";

export type SegItem<K extends string> = { key: K; label: ReactNode; count?: number };

/** The segmented control: a grey track, the current item on a white pill. Counts sit beside the label. */
export function Seg<K extends string>({ label, items, value, onChange }: {
  label: string;
  items: SegItem<K>[];
  value: K;
  onChange: (key: K) => void;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {items.map((it) => (
        <button key={it.key} type="button" aria-pressed={it.key === value} onClick={() => onChange(it.key)}>
          {it.label}
          {it.count != null && <b>{it.count.toLocaleString("en-GB")}</b>}
        </button>
      ))}
    </div>
  );
}
