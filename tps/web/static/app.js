// Submits actions as jobs, polls /job while one runs, and renders its result.
const POLL_MS = 1000;
const $ = (id) => document.getElementById(id);
let polling = null;

function el(tag, text, attrs = {}) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  Object.assign(node, attrs);
  return node;
}

function outputUrl(path) {
  return "/output/" + path.split("/").map(encodeURIComponent).join("/");
}

function setBusy(busy) {
  document.querySelectorAll("form[data-job] button[type=submit]").forEach((b) => { b.disabled = busy; });
}

function renderJob(job) {
  const box = $("job");
  if (!job) { box.hidden = true; return; }
  box.hidden = false;
  box.className = "job " + job.state;
  $("job-name").textContent = job.name;
  $("job-state").textContent = { running: "Running", done: "Done", failed: "Failed" }[job.state];
  $("job-state").className = "badge " + job.state;

  const progress = box.querySelector(".progress");
  const running = job.state === "running";
  const pct = !running ? 100 : job.total ? Math.round((job.done / job.total) * 100) : 0;
  progress.classList.toggle("indeterminate", running && !job.total);
  progress.setAttribute("aria-valuenow", pct);
  $("job-bar").style.width = pct + "%";
  $("job-message").textContent = running
    ? (job.total ? `${job.done} / ${job.total} - ${job.message}` : job.message || "Working...")
    : job.error || "";

  const result = job.result;
  $("job-summary").textContent = result ? result.summary : "";
  const actions = $("job-actions");
  actions.replaceChildren();
  for (const file of result ? result.files : []) {
    actions.append(el("a", "Download " + file.split("/").pop(), { href: outputUrl(file) }));
  }
  if (result && result.folder) {
    const open = el("button", "Open folder", { type: "button", className: "btn btn-small" });
    open.addEventListener("click", () =>
      fetch("/open-folder", { method: "POST", body: new URLSearchParams({ path: result.folder }) }));
    actions.append(open, el("span", "output/" + result.folder, { className: "muted" }));
  }

  const details = result ? result.details : [];
  $("job-details-box").hidden = details.length === 0;
  $("job-details-title").textContent = `Details (${details.length})`;
  $("job-details").replaceChildren(...details.map((line) => el("li", line)));

  setBusy(running);
}

async function poll() {
  const job = await (await fetch("/job")).json();
  renderJob(job);
  if (job && job.state === "running") {
    polling = setTimeout(poll, POLL_MS);
  } else {
    polling = null;
    if ($("logs").open) loadLogs();
  }
}

async function submitJob(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (form.dataset.confirm && !confirm(form.dataset.confirm)) return;

  let url = form.dataset.job;
  const data = new FormData(form);
  if (url === "month") {  // the Reports form: the clicked button picks the job
    url = "/jobs/" + event.submitter.value;
    data.delete("kind");
  }

  setBusy(true);
  const response = await fetch(url, { method: "POST", body: data });
  const body = await response.json();
  if (!response.ok) {
    setBusy(false);
    alert(body.error);
    return;
  }
  form.querySelectorAll("input[type=file]").forEach((input) => { input.value = ""; });
  renderJob(body);
  clearTimeout(polling);
  poll();
}

async function loadLogs() {
  const { lines } = await (await fetch("/logs")).json();
  const log = $("log-lines");
  log.textContent = lines.length ? lines.join("\n") : "No log entries yet.";
  log.scrollTop = log.scrollHeight;
}

document.querySelectorAll("form[data-job]").forEach((form) => form.addEventListener("submit", submitJob));
$("logs").addEventListener("toggle", (e) => { if (e.target.open) loadLogs(); });
$("logs-refresh").addEventListener("click", loadLogs);

const initial = JSON.parse($("initial-job").textContent);
renderJob(initial);
if (initial && initial.state === "running") poll();
