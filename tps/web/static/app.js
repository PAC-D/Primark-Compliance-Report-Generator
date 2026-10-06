// One page: pick a month, see what exists for it, generate what's missing.
// Jobs run on the server one at a time; this polls /job while one runs.
const POLL_MS = 1000;
const $ = (id) => document.getElementById(id);
const monthInput = $("month");
const rows = [...document.querySelectorAll(".row[data-kind]")];
const when = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
const fmt = new Intl.NumberFormat();
let job = JSON.parse($("initial-job").textContent);
let monthHasData = true;
let polling = null;

function el(tag, text, attrs = {}) {
  const node = Object.assign(document.createElement(tag), attrs);
  if (text) node.textContent = text;
  return node;
}

const outputUrl = (path) => "/output/" + path.split("/").map(encodeURIComponent).join("/");
const openFolder = (path) => fetch("/open-folder", { method: "POST", body: new URLSearchParams({ path }) });
const running = () => job && job.state === "running";

function showError(message) {
  $("error").textContent = message || "";
  $("error").hidden = !message;
}

function shiftMonth(delta) {
  const [y, m] = monthInput.value.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  monthInput.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  loadMonth();
}

function updateButtons() {
  const busy = running();
  rows.forEach((row) => { row.querySelector("[data-generate]").disabled = busy || !monthHasData; });
  document.querySelectorAll("form[data-job] [type=submit]").forEach((b) => { b.disabled = busy; });
  $("job-cancel").hidden = !busy;
  $("job-cancel").disabled = Boolean(job && job.cancelling);
  $("job-cancel").textContent = job && job.cancelling ? "Cancelling…" : "Cancel";
}

async function loadMonth() {
  if (!monthInput.value) return;
  const label = new Date(monthInput.value + "-01T00:00").toLocaleDateString(undefined, { month: "long", year: "numeric" });
  $("month-label").textContent = label;
  $("month-button").setAttribute("aria-label", `Report month: ${label}. Choose another month`);
  const status = await (await fetch(`/month/${monthInput.value}`)).json();
  monthHasData = status.total_suppliers > 0;
  $("month-facts").textContent = monthHasData
    ? `${fmt.format(status.total_suppliers)} suppliers · ${fmt.format(status.total_factories)} factories`
    : `No transaction data for ${label}. Load files under Data.`;

  for (const row of rows) {
    const out = status.outputs[row.dataset.kind];
    const open = row.querySelector("[data-open]");
    const statusText = row.querySelector(".row-status");
    row.querySelector("[data-generate]").textContent = out ? "Regenerate" : "Generate";
    open.hidden = !out;
    if (!out) {
      statusText.textContent = "Not generated yet";
    } else {
      const count = out.folder ? `${fmt.format(out.count)} ${row.dataset.kind === "extract" ? "workbooks" : "PDFs"} · ` : "";
      statusText.textContent = `${count}Updated ${when.format(new Date(out.updated))}`;
      open.onclick = out.file ? () => { location.href = outputUrl(out.file); } : () => openFolder(out.folder);
    }
  }
  markBusyRow();
  updateButtons();
}

function markBusyRow() {
  for (const row of rows) {
    const busy = running() && job.name.startsWith(row.querySelector("h2").textContent);
    row.classList.toggle("busy", busy);
    if (busy) {
      row.querySelector(".row-status").textContent = job.total > 1
        ? `Generating… ${job.done} of ${job.total}` : "Generating…";
    }
  }
}

function renderJob() {
  const box = $("job");
  box.hidden = !job;
  if (!job) return updateButtons();

  box.className = "activity " + job.state;
  $("job-name").textContent = job.name;
  const progress = box.querySelector(".progress");
  const pct = job.state !== "running" ? 100 : job.total ? Math.round((job.done / job.total) * 100) : 0;
  progress.classList.toggle("indeterminate", running() && !job.total);
  progress.setAttribute("aria-valuenow", pct);
  $("job-bar").style.width = pct + "%";

  const result = job.result;
  $("job-message").textContent = {
    running: job.total > 1 ? `${job.done} of ${job.total} · ${job.message}` : job.message || "Starting…",
    done: result ? result.summary : "Done",
    failed: job.error,
    cancelled: "Cancelled. Files already written are kept.",
  }[job.state];

  const actions = $("job-actions");
  actions.replaceChildren();
  for (const file of result ? result.files : []) {
    actions.append(el("a", "Download " + file.split("/").pop(), { href: outputUrl(file) }));
  }
  if (result && result.folder) {
    const button = el("button", "Show in Folder", { type: "button", className: "button" });
    button.onclick = () => openFolder(result.folder);
    actions.append(button);
  }

  const details = result ? result.details : [];
  $("job-details-box").hidden = details.length === 0;
  $("job-details-title").textContent = `Details (${details.length})`;
  $("job-details").replaceChildren(...details.map((line) => el("li", line)));

  markBusyRow();
  updateButtons();
}

async function poll() {
  job = await (await fetch("/job")).json();
  renderJob();
  if (running()) {
    polling = setTimeout(poll, POLL_MS);
  } else {
    polling = null;
    loadMonth();
    if ($("logs").open) loadLogs();
    // An import may have changed the list; don't swap out a field being edited.
    if ($("suppliers").open && !$("supplier-list").contains(document.activeElement)) loadSuppliers();
  }
}

async function startJob(url, body) {
  showError("");
  const response = await fetch(url, { method: "POST", body });
  const data = await response.json();
  if (!response.ok) return showError(data.error);
  job = data;
  renderJob();
  clearTimeout(polling);
  poll();
}

for (const row of rows) {
  row.querySelector("[data-generate]").addEventListener("click", () =>
    startJob(`/jobs/${row.dataset.kind}`, new URLSearchParams({ month: monthInput.value })));
}

document.querySelectorAll("form[data-job]").forEach((form) => form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (form.id === "clear-form") {
    const dialog = $("confirm-clear");
    dialog.showModal();
    const choice = await new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue), { once: true }));
    if (choice !== "clear") return;
  }
  await startJob(form.dataset.job, new FormData(form));
  form.querySelectorAll("input[type=file]").forEach((input) => { input.value = ""; });
}));

$("job-cancel").addEventListener("click", async () => {
  job = await (await fetch("/job/cancel", { method: "POST" })).json();
  renderJob();
});

async function loadLogs() {
  const { lines } = await (await fetch("/logs")).json();
  const log = $("log-lines");
  log.textContent = lines.length ? lines.join("\n") : "No log entries yet.";
  log.scrollTop = log.scrollHeight;
}

// Suppliers: the whole list loads once; search and filters only hide rows.
let suppliers = [];

async function loadSuppliers() {
  suppliers = await (await fetch("/suppliers")).json();
  const monthSelect = $("supplier-month");
  const chosen = monthSelect.value;
  const months = [...new Set(suppliers.flatMap((s) => Object.keys(s.months)))].sort().reverse();
  monthSelect.replaceChildren(el("option", "All months", { value: "" }), ...months.map((m) =>
    el("option", new Date(m + "-01T00:00").toLocaleDateString(undefined, { month: "long", year: "numeric" }), { value: m })));
  monthSelect.value = months.includes(chosen) ? chosen : "";
  $("supplier-list").replaceChildren(...suppliers.map(supplierRow));
  filterSuppliers();
}

function supplierRow(supplier) {
  const input = el("input", "", { type: "email", multiple: true, value: supplier.emails,
                                  className: "field", placeholder: "No email" });
  const state = el("span", "", { className: "save-state secondary" });
  input.addEventListener("input", () => { state.textContent = ""; });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") input.blur(); });
  input.addEventListener("change", async () => {
    input.value = input.value.replaceAll(";", ",");  // lists pasted from Outlook
    if (!input.reportValidity()) {
      state.textContent = "Not saved";
      return;
    }
    state.textContent = "Saving…";
    const response = await fetch("/suppliers/emails", {
      method: "POST", body: new URLSearchParams({ supplier: supplier.name, emails: input.value }) });
    if (!response.ok) {
      state.textContent = "Not saved";
      return;
    }
    supplier.emails = input.value = (await response.json()).emails;
    state.textContent = "Saved";
    filterSuppliers();
  });
  const label = el("label");
  label.append(el("span", supplier.name, { className: "supplier-name" }), input);
  supplier.row = el("li", "", { className: "supplier" });
  supplier.row.append(label, state);
  return supplier.row;
}

function filterSuppliers() {
  const query = $("supplier-search").value.trim().toLowerCase();
  const region = $("supplier-region").value;
  const month = $("supplier-month").value;
  let shown = 0, withEmails = 0;
  for (const s of suppliers) {
    // With a month picked, the region is the supplier's region in that month, as in the report folders.
    const visible = (!month || month in s.months)
      && (!region || (month ? s.months[month] : s.region) === region)
      && (!query || s.name.toLowerCase().includes(query) || s.emails.toLowerCase().includes(query));
    s.row.hidden = !visible;
    shown += visible;
    withEmails += visible && Boolean(s.emails);
  }
  const count = shown === suppliers.length ? fmt.format(shown) : `${fmt.format(shown)} of ${fmt.format(suppliers.length)}`;
  $("supplier-count").textContent = `${count} suppliers · ${fmt.format(withEmails)} with emails`;
}

$("supplier-search").addEventListener("input", filterSuppliers);
$("supplier-region").addEventListener("change", filterSuppliers);
$("supplier-month").addEventListener("change", filterSuppliers);
$("suppliers").addEventListener("toggle", (e) => { if (e.target.open) loadSuppliers(); });

$("prev-month").addEventListener("click", () => shiftMonth(-1));
$("next-month").addEventListener("click", () => shiftMonth(1));
monthInput.addEventListener("change", loadMonth);
$("month-button").addEventListener("click", () => monthInput.showPicker());
$("logs").addEventListener("toggle", (e) => { if (e.target.open) loadLogs(); });

renderJob();
loadMonth();
if (running()) poll();
