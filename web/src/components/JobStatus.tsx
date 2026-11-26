"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiGet, apiPost, errorText, outputUrl } from "@/lib/api";
import { int } from "@/lib/format";

/** GET /api/job. files and folder are paths relative to OUTPUT_DIR, served at /api/output/<path>. */
export type Job = {
  id: string;
  name: string;
  state: "running" | "done" | "failed" | "cancelled";
  done: number;
  total: number;
  message: string;
  error: string | null;
  cancelling: boolean;
  result: { summary: string; details: string[]; files: string[]; folder: string | null } | null;
};

const JOB_EVENT = "tps-job-started";
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Ids of the jobs this page started that have not yet been reported finished. */
const started = new Set<string>();

/** Whether `j` has just finished, so onFinish fires once: a job seen running that has stopped, or a job this page
 *  started that has stopped (a fast job can be done before any poll sees it running). */
export function finishedNow(was: Job | null, j: Job | null, ours: Set<string>): boolean {
  if (!j || j.state === "running") return false;
  const mine = ours.delete(j.id);
  return mine || (was?.id === j.id && was.state === "running");
}

/**
 * Starts a job (POST /api/jobs/<kind>, /api/upload, …) and tells every JobStatus on the page to show it.
 * Returns the API's message when it refuses, e.g. the 409 "<job> is still running. Wait for it to finish, or cancel it."
 */
export async function startJob(path: string, body: FormData | URLSearchParams): Promise<string | null> {
  try {
    const res = await apiPost(path, body);
    if (res.ok) {
      const job = (await res.json().catch(() => null)) as Job | null;
      if (job?.id) started.add(job.id);
    }
    window.dispatchEvent(new Event(JOB_EVENT)); // also after a 409, so the page shows the job that is running
    if (!res.ok) return await errorText(res);
  } catch (e) {
    return message(e);
  }
  return null;
}

const baseName = (p: string) => p.slice(p.lastIndexOf("/") + 1);

/** The current job: progress bar, message and Cancel while it runs (polling every second), then its result or error. */
export function JobStatus({ onFinish, onUpdate }: {
  onFinish?: (job: Job) => void;
  onUpdate?: (job: Job | null) => void; // every load, e.g. to disable a Start button while a job runs
}) {
  const [job, setJob] = useState<Job | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<Job["id"] | null>(null);
  const prev = useRef<Job | null>(null);
  const finish = useRef(onFinish);
  const update = useRef(onUpdate);
  useEffect(() => { finish.current = onFinish; update.current = onUpdate; });

  const show = useCallback((j: Job | null) => {
    const was = prev.current;
    prev.current = j;
    setJob(j);
    update.current?.(j);
    if (finishedNow(was, j, started)) finish.current?.(j!);
  }, []);

  const load = useCallback(async () => {
    try {
      show(await apiGet<Job | null>("/job"));
      setProblem(null);
    } catch (e) {
      setProblem(message(e));
    }
  }, [show]);

  useEffect(() => {
    load();
    window.addEventListener(JOB_EVENT, load);
    return () => window.removeEventListener(JOB_EVENT, load);
  }, [load]);

  const running = job?.state === "running";
  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 1000);
    return () => clearInterval(t);
  }, [running, load]);

  const cancel = async () => {
    try {
      const res = await apiPost("/job/cancel", new URLSearchParams());
      if (res.ok) show(await res.json());
      else setProblem(await errorText(res));
    } catch (e) {
      setProblem(message(e));
    }
  };

  if (!job || job.id === dismissed) return problem ? <p className="text-danger" role="alert">{problem}</p> : null;
  const share = job.total > 0 ? Math.min(100, (job.done / job.total) * 100) : 0;
  return (
    <Card className="gap-2.5 p-4.5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="mr-auto min-w-0">
          <div className="font-semibold">{job.name}</div>
          {running && job.message && <div className="text-ink2">{job.message}</div>}
        </div>
        {running && job.total > 0 && <span className="text-ink2">{int(job.done)} of {int(job.total)}</span>}
        {running ? (
          <Button variant="secondary" onClick={cancel} disabled={job.cancelling}>{job.cancelling ? "Cancelling" : "Cancel"}</Button>
        ) : (
          <Button variant="secondary" onClick={() => setDismissed(job.id)}>Dismiss</Button>
        )}
      </div>
      {running && <Progress value={share} aria-label={job.name} />}
      {/* announced: how the job ended, its result, and any problem (not every progress tick) */}
      <div className="grid gap-2.5 empty:hidden" aria-live="polite">
        {job.state === "failed" && <p className="text-danger">{job.error || "The job failed."}</p>}
        {job.state === "cancelled" && <p className="text-ink2">Cancelled.</p>}
        {job.state === "done" && job.result && (
          <>
            <p>{job.result.summary}</p>
            {job.result.details.length > 0 && (
              <ul className="grid max-h-56 gap-1 overflow-auto text-ink2">{job.result.details.map((d, i) => <li key={i}>{d}</li>)}</ul>
            )}
            {job.result.files.length > 0 && (
              <ul className="grid max-h-56 gap-1 overflow-auto">
                {job.result.files.map((f) => (
                  <li key={f}><a className="font-medium text-link hover:underline" href={outputUrl(f)} download>{baseName(f)}</a></li>
                ))}
              </ul>
            )}
            {job.result.folder && job.result.files.length === 0 && <p className="text-ink2">Saved in {job.result.folder}</p>}
          </>
        )}
        {problem && <p className="text-danger">{problem}</p>}
      </div>
    </Card>
  );
}
