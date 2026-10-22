const $ = id => document.getElementById(id);

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

  const decision = document.createElement("div");
  decision.className = "incident-decision";
  addField(decision, "Classification", row.classification);
  addField(decision, "LLM confidence", row.llm_confidence + "/100");
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
  summary.textContent = "Evidence and processing details · " + row.supporting_evidence.length + " source columns";
  details.append(summary);
  const content = document.createElement("div");
  content.className = "incident-secondary";
  addField(content, "Processing status", row.processing_status);
  addField(content, "Key root cause", row.key_root_cause);
  const evidence = document.createElement("section");
  const heading = document.createElement("h3");
  heading.textContent = "Source columns supporting the decision";
  evidence.append(heading);
  if (!row.supporting_evidence.length) {
    const empty = document.createElement("p");
    empty.textContent = "No supporting source columns returned.";
    evidence.append(empty);
  }
  for (const columnName of row.supporting_evidence) {
    const text = document.createElement("p");
    text.textContent = columnName;
    text.className = "record-text";
    evidence.append(text);
  }
  content.append(evidence);
  details.append(content);
  card.append(details);
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

async function loadDashboard() {
  $("reload").disabled = true;
  $("message").hidden = true;
  try {
    const response = await fetch("/api/dashboard", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load model results.");
    $("mode").textContent = data.demo ? "Demo · synthetic data" : "LLM results";
    $("demo-note").hidden = !data.demo;
    for (const key of ["total", "HSBC", "SUPPLIER", "failed"]) {
      $(key + "-count").textContent = data.counts[key];
    }
    $("incident-list").replaceChildren();
    $("dashboard-empty").hidden = data.records.length > 0;
    for (const row of data.records) {
      $("incident-list").append(recordCard(row));
    }
  } catch (error) {
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
$("reload").addEventListener("click", loadDashboard);
loadDashboard();
