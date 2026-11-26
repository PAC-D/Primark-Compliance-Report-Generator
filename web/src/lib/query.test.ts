import { describe, expect, it } from "vitest";
import { addMonths, monthFrom, readFilters, supplierPath, withMonth, writeFilters } from "./query";

describe("query", () => {
  it("round-trips the filters through the URL", () => {
    const q = "month=2026-08&supplier=A%20%26%20B&band=low";
    expect(writeFilters(readFilters(new URLSearchParams(q)))).toBe(q);
  });
  it("round-trips a name with an apostrophe, brackets and a dot, and a band with a page", () => {
    const f = { ...readFilters(new URLSearchParams()), supplier: "O'NEIL (UK) CO.", band: "low" as const, page: 3 };
    const q = writeFilters(f);
    expect(q).toBe("supplier=O'NEIL%20(UK)%20CO.&band=low&page=3");
    expect(readFilters(new URLSearchParams(q))).toEqual(f);
  });
  it("an unknown band falls back to all, a bad page to 1", () => {
    const f = readFilters(new URLSearchParams("band=huge&page=x"));
    expect(f.band).toBe("all");
    expect(f.page).toBe(1);
    expect(writeFilters(f)).toBe("");
    expect(readFilters(new URLSearchParams("month=2026-13")).month).toBe("");
  });
  it("round-trips approved_by with other params", () => {
    const q = "month=2026-08&region=BD&approved_by=A%20B";
    const f = readFilters(new URLSearchParams(q));
    expect(f.approved_by).toBe("A B");
    expect(writeFilters(f)).toBe(q);
  });
  it("normalises the region: bd -> BD, anything else -> all", () => {
    expect(readFilters(new URLSearchParams("region=bd")).region).toBe("BD");
    expect(readFilters(new URLSearchParams("region=cn")).region).toBe("CN");
    expect(readFilters(new URLSearchParams("region=XX")).region).toBe("");
  });
  it("monthFrom reads a valid month or null", () => {
    expect(monthFrom(new URLSearchParams("month=2026-13"))).toBeNull();
    expect(monthFrom(new URLSearchParams("month=2026-08"))).toBe("2026-08");
    expect(monthFrom(new URLSearchParams())).toBeNull();
  });
  it("withMonth carries the month on a path", () => {
    expect(withMonth("/kpi", "2026-08")).toBe("/kpi?month=2026-08");
    expect(withMonth("/kpi", null)).toBe("/kpi");
  });
  it("addMonths crosses years", () => {
    expect(addMonths("2026-01", -1)).toBe("2025-12");
    expect(addMonths("2026-08", -2)).toBe("2026-06");
  });
  it("round-trips a supplier with an apostrophe, brackets, & and a dot through ?supplier=, keeping the month", () => {
    const name = "O'NEIL (UK) & CO.";
    const path = supplierPath(name, "2026-08");
    expect(path).toBe("/supplier-compliance?month=2026-08&supplier=O'NEIL%20(UK)%20%26%20CO.");
    const f = readFilters(new URLSearchParams(path.split("?")[1]));
    expect(f.supplier).toBe(name);
    expect(f.month).toBe("2026-08");
    expect(supplierPath(name, null)).toBe("/supplier-compliance?supplier=O'NEIL%20(UK)%20%26%20CO.");
  });
  it("passes a supplier through untrimmed; all spaces means none", () => {
    const f = readFilters(new URLSearchParams("supplier=%20ACME%20LTD%20"));
    expect(f.supplier).toBe(" ACME LTD ");
    expect(readFilters(new URLSearchParams(writeFilters(f))).supplier).toBe(" ACME LTD ");
    expect(readFilters(new URLSearchParams("supplier=%20%20")).supplier).toBe("");
  });
});
