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

function recordDetails(row) {
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "Analysis and evidence";
  details.append(summary);
  const content = document.createElement("div");
  content.className = "dashboard-detail-content";
  addField(content, "Key root cause", row.key_root_cause);
  addField(content, "Decision rationale", row.decision_rationale);
  if (row.classification === "SUPPLIER") {
    for (const [label, value] of [
      ["Supplier", row.supplier_name],
      ["Product, service, or infrastructure", row.supplier_product_or_service],
      ["Supplier action, defect, or omission", row.supplier_action_or_failure],
      ["How it caused the incident or impact", row.supplier_causal_explanation],
      ["Why the supplier is accountable", row.supplier_accountability_reason]
    ]) addField(content, label, value);
    if (row.supplier_more_info) addField(content, "Additional supplier information", row.supplier_more_info);
  }
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
  const inputs = document.createElement("details");
  const inputSummary = document.createElement("summary");
  inputSummary.textContent = "Source fields";
  inputs.append(inputSummary);
  for (const [name, value] of Object.entries(row.input)) addField(inputs, name, value || "(empty)");
  content.append(inputs);
  details.append(content);
  return details;
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
    $("final-rows").replaceChildren();
    $("dashboard-empty").hidden = data.records.length > 0;
    $("final-table").hidden = data.records.length === 0;
    for (const row of data.records) {
      const tr = document.createElement("tr");
      const supplier = row.classification === "SUPPLIER";
      for (const value of [row.incident_id, row.summary, row.classification,
        supplier ? row.supplier_name : "—", supplier ? row.supplier_product_or_service : "—",
        row.llm_confidence + "/100"]) {
        const td = document.createElement("td");
        td.textContent = value;
        tr.append(td);
      }
      const detailRow = document.createElement("tr");
      detailRow.className = "dashboard-details";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 6;
      detailCell.append(recordDetails(row));
      detailRow.append(detailCell);
      $("final-rows").append(tr, detailRow);
    }
  } catch (error) {
    $("message").textContent = error.message;
    $("message").className = "message error";
    $("message").hidden = false;
    $("final-rows").replaceChildren();
    $("final-table").hidden = true;
    $("dashboard-empty").hidden = true;
    for (const element of document.querySelectorAll("[id$='-count']")) element.textContent = "—";
  } finally {
    $("reload").disabled = false;
  }
}
$("reload").addEventListener("click", loadDashboard);
loadDashboard();
