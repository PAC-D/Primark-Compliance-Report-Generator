"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { band } from "@/lib/format";
import { supplierPath } from "@/lib/query";
import { cn } from "@/lib/utils";

/** A supplier's name, linking to its Supplier Compliance page for the same month. */
export function SupplierLink({ name, month }: { name: string; month: string }) {
  return <Link className="font-medium hover:underline" href={supplierPath(name, month)}>{name}</Link>;
}

/** One dashboard section: a card with a title, an optional caption and action, arriving with the page. */
export function Section({ title, caption, action, children, className }: {
  title: string; caption?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <Card data-arrive className={className}>
      <CardHeader>
        <CardTitle className="text-base font-semibold"><h2 className="text-[length:inherit] leading-[inherit] font-[inherit]">{title}</h2></CardTitle>
        {caption && <CardDescription>{caption}</CardDescription>}
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className="px-0">{children}</CardContent>
    </Card>
  );
}

/** The band colours, as in the reports: below 40% red, 40–70% amber, 70% and up green. */
export const BAND_TEXT = { lo: "text-danger font-semibold", mid: "text-warn", hi: "text-ok" } as const;
// tints kept light so the band text stays at 4.5:1 or better on them (light mode is the tighter case)
export const BAND_CELL = { lo: "bg-danger/6 text-danger font-semibold", mid: "bg-warn/6 text-warn", hi: "" } as const;
export const bandOf = (v: number | null) => (v == null ? null : band(v));

/** A % in its band colour; "–" when missing. */
export function Rate({ value, className }: { value: number | null; className?: string }) {
  const b = bandOf(value);
  return <span className={cn(b && BAND_TEXT[b], className)}>{value == null ? "–" : `${value.toFixed(1)}%`}</span>;
}

/** A plain table scroller: the shadcn Table sits inside, its header sticks while the rows scroll. */
export const scroller = "max-h-[520px] overflow-auto border-t border-line [&_[data-slot=table-container]]:overflow-visible";
