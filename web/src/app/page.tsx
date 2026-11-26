"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { JobStatus, startJob, type Job } from "@/components/JobStatus";
import { MonthPicker } from "@/components/MonthPicker";
import { Button } from "@/components/ui/button";
import { apiGet, outputUrl } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { useArrival } from "@/lib/motion";
import { monthName, readFilters, writeFilters, type Filters } from "@/lib/query";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { AllSuppliers } from "./dashboard/AllSuppliers";
import { FollowUp, TopPerformers, Visibility } from "./dashboard/Sheets";
import { Summary } from "./dashboard/Summary";
import type { Dashboard } from "./dashboard/types";
import { Yearly } from "./dashboard/Yearly";

const SUMMARY_JOB = "Summary Workbook"; // api/routes.py JOBS["summary"]; the job is named "Summary Workbook · August 2026"
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The summary workbook on screen: its five sheets top to bottom, then the all-supplier table. */
function DashboardPage() {
  const router = useRouter();
  const path = usePathname();
  const search = useSearchParams();
  const f = useMemo(() => readFilters(new URLSearchParams(search.toString())), [search]);
  const go = (next: Filters) => router.push(`${path}?${writeFilters(next)}`, { scroll: false });

  const [latest, setLatest] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<{ month: string; d: Dashboard } | null>(null); // labels come from the loaded month
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<string | null>(null);
  const [jobProblem, setJobProblem] = useState<string | null>(null);
  const [jobRunning, setJobRunning] = useState(false);
  const [preparing, setPreparing] = useState(false); // our summary job is running, then its file downloading
  const month = f.month || latest;
  const scope = useRef<HTMLElement>(null);
  useArrival(scope, [!!loaded]);

  useEffect(() => {
    apiGet<{ month: string }>("/latest-month").then((r) => setLatest(r.month), (e) => setProblem(message(e)));
  }, []);

  useEffect(() => {
    if (!month) return;
    let live = true;
    setProblem(null);
    setLoading(true);
    apiGet<Dashboard>("/dashboard", { month })
      .then((d) => live && setLoaded({ month, d }), (e) => {
        if (!live) return;
        setLoaded(null); // never leave the last month's figures under an error
        setProblem(message(e));
      })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [month]);

  const downloadSummary = async () => {
    if (!month || preparing) return;
    setPreparing(true);
    setJobProblem(null);
    const refused = await startJob("/jobs/summary", new URLSearchParams({ month }));
    if (refused) {
      setJobProblem(refused);
      setPreparing(false);
    }
  };
  // onFinish fires for any job this page sees finish; only ours (a summary job while preparing) downloads
  const finished = async (job: Job) => {
    if (!preparing || !job.name.startsWith(SUMMARY_JOB)) return;
    const file = job.state === "done" ? job.result?.files[0] : undefined;
    if (file) {
      const name = file.slice(file.lastIndexOf("/") + 1);
      try {
        await downloadFile(outputUrl(file), name);
        toast.success("Downloaded", { description: name });
      } catch (e) {
        toast.error("Download failed", { description: message(e) });
      }
    }
    setPreparing(false);
  };

  return (
    <section ref={scope} className="flex flex-col gap-3.5">
      <div data-arrive className="head">
        <div>
          <h1>Dashboard</h1>
          <p>{month ? `Summary for ${monthName(month)}` : "Loading"}</p>
        </div>
        <div className="act">
          <MonthPicker latest={latest} value={month} onChange={(m) => go({ ...f, month: m, page: 1 })} />
          <Button onClick={downloadSummary} disabled={!loaded || preparing || jobRunning}>
            {preparing ? "Preparing…" : "Download summary workbook"}
          </Button>
        </div>
      </div>

      {problem && <p className="text-danger" role="alert">{problem}</p>}
      {jobProblem && <p className="text-danger" role="alert">{jobProblem}</p>}
      <JobStatus onFinish={finished} onUpdate={(j) => setJobRunning(j?.state === "running")} />

      {/* the old month's figures stay, dimmed, while the new month loads; then the numbers roll */}
      {loaded && (
        <div aria-busy={loading} className={cn("flex flex-col gap-3.5 transition-opacity duration-200", loading && "opacity-50")}>
          <Summary d={loaded.d} month={loaded.month} />
          <Visibility d={loaded.d} />
          <TopPerformers d={loaded.d} month={loaded.month} />
          <FollowUp d={loaded.d} month={loaded.month} />
          <Yearly d={loaded.d} month={loaded.month} />
        </div>
      )}
      {month && <AllSuppliers month={month} f={f} go={go} jobRunning={jobRunning} onJobProblem={setJobProblem} />}
    </section>
  );
}

export default function Page() {
  return <Suspense><DashboardPage /></Suspense>;
}
