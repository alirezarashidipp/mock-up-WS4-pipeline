const $ = id => document.getElementById(id);
let records = [];
let activeFilter = "total";
let supplierNames = [];
let savingReview = false;
let loadingDashboard = false;

function addField(container, label, value) {
  const section = document.createElement("section");
  const heading = document.createElement("h3");
  const text = document.createElement("p");
  heading.textContent = label;
  text.textContent = value || "Unknown";
  text.className = "record-text";
  section.append(heading, text);
  container.append(section);
}

function evidenceStrength(value) {
  if (value == null || String(value).trim() === "") return "Not recorded";
  const score = String(value).trim();
  if (!/^[0-4]$/.test(score)) return "Invalid score";
  const labels = ["Unsupported", "Weak", "Moderate", "Strong", "Very strong"];
  return score + "/4 · " + labels[Number(score)];
}

function recordCard(row) {
  const card = document.createElement("article");
  card.className = "incident-card";
  card.dataset.incidentId = row.incident_id;
  const header = document.createElement("header");
  header.className = "incident-heading";
  const id = document.createElement("p");
  id.className = "incident-id";
  id.textContent = row.incident_id;
  const title = document.createElement("h3");
  title.className = "incident-title";
  title.textContent = row.summary || "Incident details";
  header.append(id, title);
  card.append(header);

  if (row.processing_status === "failed") {
    addField(card, "Processing status", "Failed");
    addField(card, "Processing error", row.error || "No error details recorded.");
  } else {
    const decision = document.createElement("div");
    decision.className = "incident-decision";
    addField(decision, "Model classification", row.classification);
    addField(decision, "Attribution evidence strength", evidenceStrength(row.attribution_evidence_strength));
    card.append(decision);
    addField(card, "Decision rationale", row.decision_rationale);
    if (row.classification === "SUPPLIER") {
      const supplier = document.createElement("div");
      supplier.className = "supplier-grid";
      for (const [label, value] of [
        ["Supplier", row.supplier_name],
        ["Product, service, or infrastructure", row.supplier_product_or_service],
        ["Supplier action, defect, or omission", row.supplier_action_or_failure],
        ["How it caused the incident or impact", row.supplier_causal_explanation],
        ["Why the supplier is accountable", row.supplier_accountability_reason],
        ["Additional supplier information", row.supplier_more_info || "No additional information recorded."]
      ]) addField(supplier, label, value);
      card.append(supplier);
    }

    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Evidence and processing details · " + row.evidence_column.length + " source columns";
    details.append(summary);
    const content = document.createElement("div");
    content.className = "incident-secondary";
    addField(content, "Processing status", row.processing_status);
    addField(content, "Key root cause", row.key_root_cause);
    const evidence = document.createElement("section");
    const heading = document.createElement("h3");
    heading.textContent = "Source columns informing the decision";
    evidence.append(heading);
    if (!row.evidence_column.length) {
      const empty = document.createElement("p");
      empty.textContent = "No supporting source columns returned.";
      evidence.append(empty);
    }
    for (const columnName of row.evidence_column) {
      const text = document.createElement("p");
      text.textContent = columnName;
      text.className = "record-text";
      evidence.append(text);
    }
    content.append(evidence);
    details.append(content);
    card.append(details);
  }
  if (row.review) card.append(reviewControls(row));
  const inputs = document.createElement("details");
  const inputSummary = document.createElement("summary");
  inputSummary.textContent = "Source fields";
  inputs.append(inputSummary);
  const sourceFields = document.createElement("div");
  sourceFields.className = "incident-secondary";
  for (const [name, value] of Object.entries(row.input)) addField(sourceFields, name, value || "(empty)");
  inputs.append(sourceFields);
  card.append(inputs);
  return card;
}

function renderRecords() {
  const visible = records.filter(row => {
    if (activeFilter === "failed") return row.processing_status === "failed";
    if (row.processing_status !== "success") return false;
    return activeFilter === "total" || row.classification === activeFilter;
  });
  let label = "Classified incidents";
  for (const button of document.querySelectorAll("[data-filter]")) {
    const selected = button.dataset.filter === activeFilter;
    button.setAttribute("aria-pressed", String(selected));
    if (selected) label = button.querySelector("span").textContent;
  }
  $("results-heading").textContent = label;
  $("filter-summary").textContent = visible.length + (visible.length === 1 ? " incident shown" : " incidents shown");
  $("dashboard-empty").textContent = "No incidents found for " + label + ".";
  $("dashboard-empty").hidden = visible.length > 0;
  $("incident-list").replaceChildren();
  for (const row of visible) $("incident-list").append(recordCard(row));
}

function reviewStateLabel(status) {
  const labels = {
    pending: "Pending", approved: "Approved", corrected: "Corrected by reviewer",
    needs_review: "Needs more information", not_applicable: "Not applicable"
  };
  return labels[status] || "Pending";
}

function isApproved(status) {
  return status === "approved" || status === "corrected";
}

function hasModelSupplier(row) {
  const name = (row.supplier_name || "").trim().toLowerCase();
  const missing = ["", "unknown", "n/a", "n a", "none", "null", "not known", "not available"];
  return row.processing_status === "success" && row.classification === "SUPPLIER" && !missing.includes(name);
}

function actionButton(label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "button";
  button.textContent = label;
  return button;
}

function reviewPanel(row, target) {
  const review = row.review;
  const status = target === "classification" ? review.classification_review_status : review.supplier_review_status;
  const panel = document.createElement("section");
  panel.className = "classification-review-panel review-" + status;
  panel.dataset.reviewTarget = target;
  const heading = document.createElement("h3");
  heading.textContent = target === "classification" ? "1. Classification review" : "2. Supplier name review";
  const badge = document.createElement("span");
  badge.className = "classification-review-badge";
  badge.textContent = reviewStateLabel(status);
  panel.append(heading, badge);
  const savedValue = target === "classification" ? review.reviewed_classification : review.reviewed_supplier_name;
  const savedReason = target === "classification" ? review.classification_review_reason : review.supplier_review_reason;
  if (savedValue) addField(panel, "Human decision", savedValue);
  if (savedReason) addField(panel, "Saved reason", savedReason);

  if (target === "supplier" && (!isApproved(review.classification_review_status) || review.reviewed_classification !== "SUPPLIER")) {
    const note = document.createElement("p");
    note.className = "field-note";
    note.textContent = review.reviewed_classification === "HSBC"
      ? "No supplier name review is needed for HSBC."
      : "Approve or correct the classification to SUPPLIER first.";
    panel.append(note);
    return panel;
  }

  const canApprove = target === "classification"
    ? row.processing_status === "success" && ["HSBC", "SUPPLIER"].includes(row.classification)
    : hasModelSupplier(row);
  const proposedValue = target === "classification" ? row.classification : row.supplier_name;
  const note = document.createElement("p");
  note.className = "field-note";
  note.textContent = canApprove
    ? "Approve the model's " + (target === "classification" ? "classification: " : "supplier name: ") + proposedValue + ". Choose No to correct it."
    : "Choose a human decision and explain it. If evidence is insufficient, keep the review open.";
  panel.append(note);

  const error = document.createElement("p");
  error.className = "classification-review-error";
  error.setAttribute("role", "alert");
  error.hidden = true;
  const actions = document.createElement("div");
  actions.className = "classification-review-actions";
  if (canApprove) {
    const approve = actionButton("Approved");
    approve.addEventListener("click", () => saveReview(row, target, {decision: "approved"}, panel, error));
    actions.append(approve);
  }
  const change = actionButton(canApprove ? "No" : "Record human decision");
  actions.append(change);
  panel.append(actions);

  const form = document.createElement("form");
  form.className = "classification-review-form";
  form.hidden = true;
  const choiceLabel = document.createElement("label");
  choiceLabel.textContent = target === "classification" ? "Correct classification" : "Select supplier";
  const choice = document.createElement("select");
  choice.required = true;
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choose an option";
  choice.append(placeholder);
  const options = target === "classification" ? ["HSBC", "SUPPLIER"] : supplierNames;
  for (const name of options) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    choice.append(option);
  }
  const unresolved = document.createElement("option");
  unresolved.value = "__needs_review__";
  unresolved.textContent = target === "classification" ? "Cannot determine yet" : "Cannot determine / supplier not listed";
  choice.append(unresolved);
  choiceLabel.append(choice);
  form.append(choiceLabel);
  if (target === "supplier" && !supplierNames.length) {
    const missing = document.createElement("p");
    missing.className = "field-note";
    missing.textContent = "Supplier choices are unavailable. Restore SUPPLIER_NAME.csv to select a supplier, or leave this review open.";
    form.append(missing);
  }
  const reasonLabel = document.createElement("label");
  reasonLabel.textContent = "Reason (required)";
  const reason = document.createElement("textarea");
  reason.required = true;
  reason.maxLength = 2000;
  reason.rows = 3;
  reasonLabel.append(reason);
  form.append(reasonLabel);
  const formActions = document.createElement("div");
  formActions.className = "classification-review-actions";
  const save = actionButton("Save human decision");
  save.type = "submit";
  const cancel = actionButton("Cancel");
  formActions.append(save, cancel);
  form.append(formActions);
  change.addEventListener("click", () => {
    form.hidden = false;
    error.hidden = true;
    choice.focus();
  });
  cancel.addEventListener("click", () => {
    form.hidden = true;
    error.hidden = true;
    change.focus();
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!reason.value.trim()) {
      error.textContent = "Write a reason before saving this decision.";
      error.hidden = false;
      reason.focus();
      return;
    }
    const decision = {
      decision: choice.value === "__needs_review__" ? "needs_review" : "corrected",
      reason: reason.value.trim()
    };
    if (decision.decision === "corrected") {
      if (target === "classification") decision.classification = choice.value;
      else decision.supplier_name = choice.value;
    }
    saveReview(row, target, decision, panel, error);
  });
  panel.append(form, error);
  return panel;
}

function reviewControls(row) {
  const section = document.createElement("section");
  section.className = "classification-review";
  if (row.review.review_stale) {
    const stale = document.createElement("p");
    stale.className = "classification-review-error";
    stale.textContent = "The source result changed. Previous approval no longer applies; review this incident again.";
    section.append(stale);
  }
  const panels = document.createElement("div");
  panels.className = "classification-review-grid";
  panels.append(reviewPanel(row, "classification"), reviewPanel(row, "supplier"));
  section.append(panels);
  const state = document.createElement("p");
  state.className = "classification-review-readiness";
  const review = row.review;
  if (!isApproved(review.classification_review_status)) state.textContent = "Awaiting classification review.";
  else if (review.reviewed_classification === "HSBC") state.textContent = "Review complete · HSBC. No supplier linking required.";
  else if (!isApproved(review.supplier_review_status)) state.textContent = "Awaiting supplier name review.";
  else state.textContent = "Ready for linking · human classification and supplier name are approved.";
  section.append(state);
  return section;
}

function showDashboard(data) {
  $("mode").textContent = data.demo ? "Demo · synthetic data" : "Classification review";
  $("demo-note").hidden = !data.demo;
  for (const key of ["total", "HSBC", "SUPPLIER", "UNCERTAIN", "failed"]) {
    $(key + "-count").textContent = data.counts[key];
  }
  for (const key of ["classification_approved", "classification_pending", "supplier_pending", "ready_for_linking"]) {
    $("review-" + key + "-count").textContent = data.review_counts ? data.review_counts[key] : "—";
  }
  supplierNames = data.supplier_names || [];
  $("supplier-catalog-note").textContent = data.supplier_catalog_note || "";
  $("supplier-catalog-note").hidden = !data.supplier_catalog_note;
  records = data.records;
  renderRecords();
}

async function saveReview(row, target, decision, panel, error) {
  if (savingReview || loadingDashboard) return;
  savingReview = true;
  error.hidden = true;
  const controls = [...document.querySelectorAll("button, select, textarea")];
  const disabledStates = controls.map(control => control.disabled);
  for (const control of controls) control.disabled = true;
  panel.setAttribute("aria-busy", "true");
  try {
    const response = await fetch("/api/classification-review", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({INCIDENT_ID: row.incident_id, version: row.review.review_version, target, ...decision})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not save the review. Refresh and try again.");
    showDashboard(data);
    const savedCard = [...document.querySelectorAll(".incident-card")].find(card => card.dataset.incidentId === row.incident_id);
    if (savedCard) {
      const savedPanel = savedCard.querySelector('[data-review-target="' + target + '"]');
      savedPanel.tabIndex = -1;
      savedPanel.focus({preventScroll: true});
    }
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
  } finally {
    savingReview = false;
    panel.removeAttribute("aria-busy");
    controls.forEach((control, index) => { control.disabled = disabledStates[index]; });
  }
}

async function loadDashboard() {
  if (savingReview || loadingDashboard) return;
  loadingDashboard = true;
  const controls = [...document.querySelectorAll("#incident-list button, #incident-list select, #incident-list textarea")];
  const disabledStates = controls.map(control => control.disabled);
  for (const control of controls) control.disabled = true;
  $("reload").disabled = true;
  for (const button of document.querySelectorAll("[data-filter]")) button.disabled = true;
  $("message").hidden = true;
  try {
    const response = await fetch("/api/dashboard", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load model results.");
    showDashboard(data);
    for (const button of document.querySelectorAll("[data-filter]")) button.disabled = false;
  } catch (error) {
    records = [];
    $("filter-summary").textContent = "";
    $("message").textContent = error.message;
    $("message").className = "message error";
    $("message").hidden = false;
    $("incident-list").replaceChildren();
    $("dashboard-empty").hidden = true;
    $("supplier-catalog-note").hidden = true;
    for (const element of document.querySelectorAll("[id$='-count']")) element.textContent = "—";
  } finally {
    loadingDashboard = false;
    controls.forEach((control, index) => { control.disabled = disabledStates[index]; });
    $("reload").disabled = false;
  }
}
for (const button of document.querySelectorAll("[data-filter]")) {
  button.addEventListener("click", () => {
    activeFilter = button.dataset.filter;
    renderRecords();
  });
}
$("reload").addEventListener("click", loadDashboard);
loadDashboard();
