import { describe, expect, it } from "vitest";
import { band, int, meterBars, pct, points, signOf } from "./format";

describe("format", () => {
  it("pct", () => {
    expect(pct(61.4)).toBe("61.4%");
    expect(pct(null)).toBe("–");
  });
  it("points uses a real minus sign", () => {
    expect(points(-6.4)).toBe("−6.4 pts");
    expect(points(3.1)).toBe("+3.1 pts");
    expect(points(0)).toBe("+0.0 pts");
    expect(points(-0.04)).toBe("+0.0 pts");
  });
  it("band thresholds are 70 and 40", () => {
    expect(band(70)).toBe("hi");
    expect(band(69.9)).toBe("mid");
    expect(band(40)).toBe("mid");
    expect(band(39.9)).toBe("lo");
  });
  it("meterBars", () => {
    expect(meterBars(22.1)).toBe(1);
    expect(meterBars(97.4)).toBe(5);
    expect(meterBars(-5)).toBe(0);
    expect(meterBars(140)).toBe(5);
  });
  it("int groups en-GB", () => {
    expect(int(14700)).toBe("14,700");
  });
  it("signOf uses U+2212 for negatives", () => {
    expect(signOf(-3)).toBe("−");
    expect(signOf(3)).toBe("+");
    expect(signOf(0)).toBe("");
    expect(signOf(-0.04, 1)).toBe(""); // rounds to zero: no sign
    expect(signOf(-0.06, 1)).toBe("−");
    expect(signOf(-0.05, 1)).toBe("−");
    expect(signOf(0.05, 1)).toBe("+");
  });
});
