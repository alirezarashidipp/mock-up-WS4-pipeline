const $ = id => document.getElementById(id);
let records = [];
let activeFilter = "total";

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
    addField(decision, "Classification", row.classification);
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

async function loadDashboard() {
  $("reload").disabled = true;
  for (const button of document.querySelectorAll("[data-filter]")) button.disabled = true;
  $("message").hidden = true;
  try {
    const response = await fetch("/api/dashboard", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load model results.");
    $("mode").textContent = data.demo ? "Demo · synthetic data" : "LLM results";
    $("demo-note").hidden = !data.demo;
    for (const key of ["total", "HSBC", "SUPPLIER", "UNCERTAIN", "failed"]) {
      $(key + "-count").textContent = data.counts[key];
    }
    records = data.records;
    renderRecords();
    for (const button of document.querySelectorAll("[data-filter]")) button.disabled = false;
  } catch (error) {
    records = [];
    $("filter-summary").textContent = "";
    $("message").textContent = error.message;
    $("message").className = "message error";
    $("message").hidden = false;
    $("incident-list").replaceChildren();
    $("dashboard-empty").hidden = true;
    for (const element of document.querySelectorAll("[id$='-count']")) element.textContent = "—";
  } finally {
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
