const $ = id => document.getElementById(id);
let records = [], selectedId = null, formIncidentId = null, busy = false, unavailable = true;

function text(id, value) { $(id).textContent = value || "Not provided"; }
function message(value, error = false) {
  $("message").textContent = value;
  $("message").className = "message" + (error ? " error" : "");
  $("message").hidden = !value;
}
function selected() { return records.find(row => row.incident_id === selectedId); }
function actionable(row) { return row && row.review_status === "PENDING_REVIEW"; }
function setControls() {
  $("reload").disabled = busy;
  $("queue-filter").disabled = busy;
  for (const button of $("queue").querySelectorAll("button")) button.disabled = busy;
  for (const id of ["final-class", "user-reason", "finalize"]) {
    $(id).disabled = busy || unavailable || !actionable(selected());
  }
}
function visibleRows() {
  const view = $("queue-filter").value;
  return records.filter(row => view === "all" ||
    (view === "pending" && actionable(row)) ||
    (view === "finalized" && row.review_status === "FINALIZED") ||
    (actionable(row) && row.result.classification === view));
}
function updateActionHint() {
  const row = selected(), choice = $("final-class").value;
  if (!row || !choice) { text("action-hint", "Choose the accountable party and explain your decision."); return; }
  const original = row.result.classification;
  const action = original === "UNDECIDED" ? "Resolve the model's uncertainty" : choice === original ? "Confirm the model's decision" : "Correct the model's decision";
  text("action-hint", action + " as " + choice + ". Your reason is required.");
}
function renderEvidence(items) {
  const container = $("supporting-evidence"); container.replaceChildren();
  if (!items.length) { container.textContent = "No supporting evidence supplied."; return; }
  for (const item of items) {
    const quote = document.createElement("blockquote"), value = document.createElement("p"), source = document.createElement("cite");
    value.textContent = item.quote; source.textContent = item.column;
    quote.append(value, source); container.append(quote);
  }
}
function renderInputs(row) {
  $("model-input").replaceChildren();
  for (const field of row.model_input) {
    const section = document.createElement("section");
    const name = document.createElement("h3"), definition = document.createElement("p"), value = document.createElement("p");
    name.textContent = field.name;
    definition.className = "field-definition"; definition.textContent = field.description;
    value.className = "source-value"; value.textContent = field.value || "(empty)";
    section.append(name, definition, value); $("model-input").append(section);
  }
  text("field-count", String(row.model_input.length) + " fields");
  $("source-details").open = row.result.classification === "UNDECIDED";
}
function render() {
  const visible = visibleRows();
  if (!visible.some(row => row.incident_id === selectedId)) selectedId = visible[0]?.incident_id || null;
  $("queue").replaceChildren(); text("queue-count", String(visible.length));
  for (const row of visible) {
    const button = document.createElement("button"); button.className = "queue-item"; button.type = "button";
    button.setAttribute("aria-current", String(row.incident_id === selectedId));
    const label = row.result.classification === "UNDECIDED" ? "LLM: I am not sure" : "LLM: " + row.result.classification;
    for (const [className, value] of [["queue-id", row.incident_id], ["queue-title", row.input.INCIDENT_SHORT_DESCRIPTION], ["queue-meta", label + (row.final_class ? " → Final: " + row.final_class : "")]]) {
      const span = document.createElement("span"); span.className = className; span.textContent = value || "Untitled incident"; button.append(span);
    }
    button.addEventListener("click", () => { selectedId = row.incident_id; render(); });
    $("queue").append(button);
  }
  const row = selected();
  $("record").hidden = !row; $("empty-state").hidden = !!row;
  if (!row) { text("empty-title", unavailable ? "Results unavailable" : "Nothing in this queue"); formIncidentId = null; setControls(); return; }
  text("record-id", row.incident_id); text("record-title", row.input.INCIDENT_SHORT_DESCRIPTION);
  text("record-service", row.input.CONFIGURATION_ITEM_NAME);
  text("review-status", row.review_status === "FINALIZED" ? "Finalized · " + new Date(row.review_date).toLocaleString() : "Awaiting your decision");
  const uncertain = row.result.classification === "UNDECIDED";
  text("classification", uncertain ? "I am not sure" : row.result.classification);
  $("assessment").classList.toggle("uncertain", uncertain);
  text("rationale-label", uncertain ? "Why the model could not decide" : "Decision rationale");
  text("rationale", uncertain ? row.result.uncertainty_reason : row.result.decision_rationale);
  text("confidence", "LLM confidence: " + row.result.llm_confidence + "/100");
  text("root-cause", row.result.key_root_cause || "Root cause has not been established.");
  text("decision-detail", row.result.decision_rationale);
  renderEvidence(row.result.supporting_evidence); renderInputs(row);
  const finalized = row.review_status === "FINALIZED";
  $("decision-form").hidden = finalized; $("final-decision").hidden = !finalized;
  if (finalized) {
    text("saved-final-class", row.final_class);
    text("saved-user-reason", row.user_reason);
    text("saved-review-action", row.review_action.replaceAll("_", " "));
  } else if (formIncidentId !== row.incident_id) {
    $("final-class").value = uncertain ? "" : row.result.classification;
    $("user-reason").value = "";
  }
  formIncidentId = row.incident_id;
  updateActionHint(); setControls();
}
async function loadQueue() {
  busy = true; setControls();
  try {
    const response = await fetch("/api/review", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not read classification results.");
    records = data.records; unavailable = false;
    text("mode", data.demo ? "Demo · synthetic data" : "Classification results");
    $("demo-note").hidden = !data.demo;
    for (const name of ["pending", "finalized", "undecided"]) text(name + "-count", String(data.counts[name]));
    text("loaded-count", String(records.length + data.counts.failed) + " records loaded");
    $("failed-note").hidden = !data.counts.failed;
    text("failed-note", String(data.counts.failed) + " pipeline failures require a new classification run.");
  } catch (error) { unavailable = true; message(error.message, true); }
  finally { busy = false; render(); }
}
async function saveDecision(event) {
  event.preventDefault();
  const row = selected(), finalClass = $("final-class").value, reason = $("user-reason").value.trim();
  if (busy || unavailable || !actionable(row)) return;
  if (!finalClass || !reason) { message("Choose HSBC or SUPPLIER and provide a reason.", true); return; }
  busy = true; setControls(); message("Saving your final decision…");
  try {
    const response = await fetch("/api/review", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({incident_id: row.incident_id, version: row.version, final_class: finalClass, user_reason: reason})
    });
    const data = await response.json();
    if (!response.ok) {
      message(data.error || "The final decision could not be saved.", true);
      if (response.status === 409) await loadQueue();
      return;
    }
    message(data.message); formIncidentId = null; await loadQueue();
  } catch {
    unavailable = true; message("Save could not be confirmed. Your reason is kept; reload to check the saved state.", true);
  } finally { busy = false; setControls(); }
}
$("decision-form").addEventListener("submit", saveDecision);
$("final-class").addEventListener("change", updateActionHint);
$("queue-filter").addEventListener("change", render);
$("reload").addEventListener("click", () => { message(""); loadQueue(); });
loadQueue();
