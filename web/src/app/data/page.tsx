"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { JobStatus, startJob, type Job } from "@/components/JobStatus";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { apiGet } from "@/lib/api";
import { useArrival } from "@/lib/motion";
import { Section } from "../dashboard/parts";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function Page() {
  const [lines, setLines] = useState<string[]>([]);
  const [logProblem, setLogProblem] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const startingNow = useRef(false);
  const [jobRunning, setJobRunning] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [chosen, setChosen] = useState(0);
  const [reload, setReload] = useState(false);
  const scope = useRef<HTMLElement>(null);
  useArrival(scope, []);

  const loadLog = useCallback(() => {
    apiGet<{ lines: string[] }>("/logs").then((r) => { setLines(r.lines); setLogProblem(null); }, (e) => setLogProblem(message(e)));
  }, []);
  useEffect(loadLog, [loadLog]);

  const onFinish = useCallback((j: Job) => {
    loadLog();
    if (j.state === "done") toast.success(j.name, { description: j.result?.summary });
    else if (j.state === "failed") toast.error(j.name, { description: j.error || "The job failed." });
  }, [loadLog]);

  const run = async (path: string, body: FormData | URLSearchParams) => {
    if (startingNow.current) return true;
    startingNow.current = true;
    setStarting(true);
    const refused = await startJob(path, body);
    if (refused) toast.error("Could not start", { description: refused });
    setStarting(false);
    startingNow.current = false;
    return refused !== null;
  };

  const upload = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const refused = await run("/upload", new FormData(form)); // an unticked box sends nothing, so the API does not reprocess
    if (!refused) { form.reset(); setChosen(0); setReload(false); } // keep the choice if it was refused, to try again
  };

  const clear = async () => {
    setConfirming(false);
    await run("/clear", new URLSearchParams());
  };

  const busy = starting || jobRunning;
  return (
    <section ref={scope} className="flex flex-col gap-3.5">
      <div className="head">
        <div>
          <h1>Data</h1>
          <p>Load transaction files and keep the database tidy.</p>
        </div>
      </div>

      <Section title="Load transaction files">
        <form className="flex flex-col gap-3 px-4.5" onSubmit={upload}>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink2">Excel files (.xlsx or .xls)</span>
            <Input type="file" name="files" accept=".xlsx,.xls" multiple onChange={(e) => setChosen(e.target.files?.length ?? 0)} />
          </label>
          <label className="flex items-center gap-2">
            <Checkbox name="reprocess" value="1" checked={reload} onCheckedChange={(c) => setReload(c === true)} /> Re-load files already loaded
          </label>
          <div><Button type="submit" disabled={busy || chosen === 0}>Load files</Button></div>
        </form>
      </Section>

      <Section title="Clear database">
        <div className="px-4.5"><Button variant="destructive" onClick={() => setConfirming(true)} disabled={busy}>Clear database</Button></div>
      </Section>
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear the database?</DialogTitle>
            <DialogDescription>This deletes all transaction rows. Supplier emails are kept. It cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirming(false)}>Keep them</Button>
            <Button variant="destructive" onClick={clear} disabled={busy}>Delete all rows</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <JobStatus onUpdate={(j: Job | null) => setJobRunning(j?.state === "running")} onFinish={onFinish} />

      <Section title="Recent log" action={<Button variant="secondary" onClick={loadLog}>Refresh</Button>}>
        <div className="px-4.5">
          {logProblem && <p className="text-danger" role="alert">{logProblem}</p>}
          {lines.length === 0 ? <p className="text-ink2">Nothing logged yet.</p> : (
            <pre className="max-h-80 overflow-auto text-xs whitespace-pre-wrap text-ink2" tabIndex={0} aria-label="Recent log">{lines.join("\n")}</pre>
          )}
        </div>
      </Section>
    </section>
  );
}
