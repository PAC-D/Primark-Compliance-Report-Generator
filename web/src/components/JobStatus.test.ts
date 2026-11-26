import { describe, expect, it } from "vitest";
import { finishedNow, type Job } from "./JobStatus";

const job = (id: string, state: Job["state"]): Job =>
  ({ id, name: "Summary Workbook · August 2026", state, done: 0, total: 1, message: "", error: null, cancelling: false, result: null });

describe("finishedNow", () => {
  it("fires once for a job we started that was never seen running", () => {
    const ours = new Set(["b"]);
    expect(finishedNow(job("a", "done"), job("b", "done"), ours)).toBe(true);
    expect(finishedNow(job("b", "done"), job("b", "done"), ours)).toBe(false); // the next poll
  });
  it("fires when a job seen running stops", () => {
    expect(finishedNow(job("a", "running"), job("a", "failed"), new Set())).toBe(true);
  });
  it("does not fire for someone else's finished job, or one still running", () => {
    expect(finishedNow(null, job("a", "done"), new Set())).toBe(false);
    const ours = new Set(["b"]);
    expect(finishedNow(null, job("b", "running"), ours)).toBe(false);
    expect(ours.has("b")).toBe(true);
  });
});
