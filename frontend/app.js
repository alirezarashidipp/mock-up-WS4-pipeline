const $ = id => document.getElementById(id);
let records = [], selectedId = null, busy = false, unavailable = true;
function text(id, value) { $(id).textContent = value || "Not provided"; }
function message(value, error = false) {
  $("message").textContent = value;
  $("message").className = "message" + (error ? " error" : "");
  $("message").hidden = !value;
}
function selected() { return records.find(row => row.row_id === selectedId); }
function actionable(row) { return row && row.review_status === "Pending Review" && ["SUPPLIER", "HSBC"].includes(row.result.classification); }
function setControls() {
  $("reload").disabled = busy;
  $("queue-filter").disabled = busy;
  for (const button of $("queue").querySelectorAll("button")) button.disabled = busy;
  for (const id of ["approve", "reject", "confirm-reject", "cancel-reject"]) $(id).disabled = busy || unavailable || !actionable(selected());
  $("rejection-reason").disabled = busy;
}
function visibleRows() {
  const view = $("queue-filter").value;
  return records.filter(row => view === "all" ||
    (view === "pending" && row.review_status === "Pending Review") ||
    (view === "approved" && row.review_status === "Approved") ||
    (view === "human" && ["Rejected", "Needs Human Review"].includes(row.review_status)));
}
function closeRejection() { $("rejection-panel").hidden = true; $("rejection-reason").value = ""; }
function showField() {
  const row = selected();
  text("field-value", row?.input[$("field-selector").value]);
}
function renderEvidence(id, raw) {
  const container = $(id); container.replaceChildren();
  let items = [];
  try { items = JSON.parse(raw || "[]"); } catch { }
  if (!Array.isArray(items) || !items.length) { container.textContent = "No supporting evidence supplied."; return; }
  for (const item of items) {
    const quote = document.createElement("blockquote"), value = document.createElement("p"), source = document.createElement("cite");
    value.textContent = item.quote; source.textContent = item.column;
    quote.append(value, source); container.append(quote);
  }
}
function render() {
  const visible = visibleRows();
  if (!visible.some(row => row.row_id === selectedId)) { selectedId = visible[0]?.row_id || null; closeRejection(); }
  $("queue").replaceChildren();
  text("queue-count", String(visible.length));
  for (const row of visible) {
    const button = document.createElement("button"); button.className = "queue-item"; button.type = "button";
    button.setAttribute("aria-current", String(row.row_id === selectedId));
    for (const [className, value] of [["queue-id", row.row_id], ["queue-title", row.input.INCIDENT_SUMMARY], ["queue-meta", row.result.classification === "UNDECIDED" ? "I am not sure" : row.result.classification]]) {
      const span = document.createElement("span"); span.className = className; span.textContent = value || "Untitled incident"; button.append(span);
    }
    button.addEventListener("click", () => { selectedId = row.row_id; closeRejection(); render(); });
    $("queue").append(button);
  }
  const row = selected();
  $("record").hidden = !row; $("empty-state").hidden = !!row;
  if (!row) { text("empty-title", unavailable ? "Results unavailable" : "Nothing in this queue"); setControls(); return; }
  text("record-id", row.row_id); text("record-title", row.input.INCIDENT_SUMMARY);
  text("record-service", row.input.INCIDENT_CONFIGURATION_ITEM);
  text("review-status", row.review_status + (row.review_date ? " · " + row.review_date : ""));
  const uncertain = row.result.classification === "UNDECIDED";
  text("classification", uncertain ? "I am not sure" : row.result.classification);
  $("assessment").classList.toggle("uncertain", uncertain);
  text("rationale-label", uncertain ? "Why the model could not decide" : "Decision rationale");
  text("rationale", uncertain ? row.result.uncertainty_reason : row.result.decision_rationale);
  text("confidence", "LLM confidence: " + row.result.llm_confidence + "/100");
  const routed = ["Rejected", "Needs Human Review"].includes(row.review_status);
  $("routing-note").hidden = !routed;
  text("routing-note", row.review_source === "USER_REJECTED" ? "User rejected: " + row.reason_of_rejection : "Automatically sent to human review. A human decision is required.");
  $("actions").hidden = !actionable(row);
  $("field-selector").replaceChildren();
  for (const key of Object.keys(row.input)) {
    const option = document.createElement("option"); option.value = key; option.textContent = key; $("field-selector").append(option);
  }
  $("field-selector").value = "INCIDENT_DESCRIPTION" in row.input ? "INCIDENT_DESCRIPTION" : Object.keys(row.input)[0];
  showField(); text("field-count", String(Object.keys(row.input).length) + " fields");
  renderEvidence("supporting-evidence", row.result.supporting_evidence);
  text("root-cause", row.result.key_root_cause || "Root cause has not been established.");
  text("decision-detail", row.result.decision_rationale);
  setControls();
}
async function loadQueue(sync = false) {
  busy = true; setControls();
  try {
    const response = await fetch(sync ? "/api/reload" : "/api/review", sync ? {method:"POST",headers:{"Content-Type":"application/json"},body:"{}"} : {cache:"no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not read classification results.");
    records = data.records; unavailable = false;
    text("mode", data.demo ? "Demo · synthetic data" : "Classification results");
    $("demo-note").hidden = !data.demo;
    for (const name of ["pending","human_review","approved"]) text(name + "-count", String(data.counts[name]));
    text("loaded-count", String(records.length + data.counts.failed) + " records loaded");
    $("failed-note").hidden = !data.counts.failed;
    text("failed-note", String(data.counts.failed) + " records failed classification and require a pipeline rerun.");
  } catch (error) { unavailable = true; message(error.message, true); }
  finally { busy = false; render(); }
}
async function saveDecision(decision) {
  const row = selected();
  if (busy || unavailable || !actionable(row)) return;
  const reason = $("rejection-reason").value.trim();
  if (decision === "Rejected" && !reason) { message("Add a reason before sending this record to human review.", true); $("rejection-reason").focus(); return; }
  busy = true; setControls(); message("Saving your decision…");
  try {
    const response = await fetch("/api/review", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({row_id:row.row_id,version:row.version,decision,reason_of_rejection:decision === "Rejected" ? reason : ""})});
    const data = await response.json();
    if (!response.ok) {
      message(data.error || "The decision could not be saved.", true);
      if (response.status === 409) await loadQueue();
      return;
    }
    message(data.message); closeRejection(); await loadQueue();
  } catch { unavailable = true; message("Save could not be confirmed. Your reason is kept; reload before retrying.", true); }
  finally { busy = false; setControls(); }
}
$("queue-filter").addEventListener("change", () => { closeRejection(); render(); });
$("field-selector").addEventListener("change", showField);
$("reload").addEventListener("click", () => { message(""); loadQueue(true); });
$("approve").addEventListener("click", () => saveDecision("Approved"));
$("reject").addEventListener("click", () => { $("rejection-panel").hidden = false; $("rejection-reason").focus(); });
$("cancel-reject").addEventListener("click", closeRejection);
$("confirm-reject").addEventListener("click", () => saveDecision("Rejected"));
loadQueue();
