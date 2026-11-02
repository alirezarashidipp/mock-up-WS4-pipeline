const $ = id => document.getElementById(id);
let records = [];
let supplierNames = [];
let activeFilter = "total";
let expandedId = readHash();
let busy = false;
let engagementCache = new Map();

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function addField(container, label, value) {
  const field = element("section", "field");
  field.append(element("h4", "", label));
  const text = value === null || value === undefined || value === "" ? "Not recorded" : String(value);
  field.append(element("p", "record-text", text));
  container.append(field);
}

function button(label, action, className = "button") {
  const control = element("button", className, label);
  control.type = "button";
  control.addEventListener("click", action);
  return control;
}

function disclosure(title) {
  const details = element("details", "detail-section");
  details.append(element("summary", "", title));
  return details;
}

function evidenceStrength(value) {
  if (value === null || value === undefined || String(value).trim() === "") return "Not recorded";
  const score = String(value).trim();
  if (!/^[0-4]$/.test(score)) return "Invalid score";
  const labels = ["Unsupported", "Weak", "Moderate", "Strong", "Very strong"];
  return score + "/4 · " + labels[Number(score)];
}

function readHash() {
  try { return decodeURIComponent(location.hash.slice(1)); }
  catch { return ""; }
}

function setExpandedId(id) {
  expandedId = id;
  const url = location.pathname + location.search + (id ? "#" + encodeURIComponent(id) : "");
  history.replaceState(null, "", url);
}

function usableModelSupplier(row) {
  const name = (row.supplier_name || "").trim().toLowerCase();
  const missing = ["", "unknown", "n/a", "n a", "none", "null", "not known", "not available"];
  return row.processing_status === "success" && row.classification === "SUPPLIER" && !missing.includes(name);
}

function reviewBadge(status, complete) {
  let label = "Pending";
  if (status === "approved") label = "Approved";
  if (status === "disagree") label = complete ? "Corrected by reviewer" : "Disagreed · unresolved";
  if (status === "not_applicable") label = "Not applicable";
  return element("span", "badge " + (complete ? "confirmed" : ""), label);
}

function modelLabel(row) {
  if (row.processing_status === "failed") return "Processing failure";
  if (row.processing_status === "pending") return "Awaiting processing";
  return row.classification || "Not classified";
}

function sourceFields(row) {
  if (Array.isArray(row.input_fields)) return row.input_fields;
  return Object.entries(row.input_fields || {}).map(([name, value]) => ({name, value}));
}

function incidentTitle(row) {
  const values = sourceFields(row);
  for (const name of ["SHORT_DESCRIPTION", "INCIDENT_SHORT_DESCRIPTION", "INCIDENT_DESCRIPTION", "IT_PROBLEM_DESCRIPTION"]) {
    const field = values.find(item => item.name === name && item.value);
    if (field) return String(field.value);
  }
  return row.key_root_cause || "Incident details";
}

function recordCard(row) {
  const card = element("details", "incident-card");
  card.dataset.incidentId = row.incident_id;
  card.open = row.incident_id === expandedId;
  const summary = element("summary", "incident-summary");
  const title = element("div", "incident-heading");
  title.append(element("span", "incident-id", row.incident_id));
  title.append(element("h3", "incident-title", incidentTitle(row)));
  const badges = element("div", "summary-badges");
  badges.append(element("span", "badge model-badge", modelLabel(row)));
  if (row.effective_supplier_name) badges.append(element("span", "supplier-label", row.effective_supplier_name));
  badges.append(element("span", "badge " + (row.review_complete ? "confirmed" : ""), row.review_complete ? "Review complete" : "Pending review"));
  summary.append(title, badges);
  card.append(summary);
  const body = element("div", "incident-body");
  card.append(body);
  let mounted = false;
  function mount() {
    if (mounted) return;
    mounted = true;
    const steps = element("div", "review-steps");
    steps.append(classificationPanel(row), supplierPanel(row), engagementPanel(row));
    body.append(steps, modelDetails(row), inputDetails(row));
  }
  if (card.open) mount();
  card.addEventListener("toggle", () => {
    if (!card.isConnected) return;
    if (card.open) {
      setExpandedId(row.incident_id);
      for (const other of document.querySelectorAll(".incident-card[open]")) {
        if (other !== card) other.open = false;
      }
      mount();
    } else if (expandedId === row.incident_id) {
      setExpandedId("");
    }
  });
  return card;
}

function panelHeader(row, target, number, title, complete) {
  const panel = element("section", "review-panel" + (complete ? " review-complete" : ""));
  panel.dataset.reviewTarget = target;
  panel.tabIndex = -1;
  const header = element("div", "step-heading");
  header.append(element("span", "step-number", number));
  header.append(element("h3", "", title));
  const badge = reviewBadge(row[target + "_review_status"], complete);
  if (target === "engagement" && row.engagement_review_status === "disagree" && !row.reviewed_engagement_id) {
    badge.textContent = "Rejected · no engagement accepted";
    badge.className = "badge rejected";
  }
  panel.append(header, badge);
  const value = target === "classification" ? row.reviewed_classification : target === "supplier" ? row.reviewed_supplier_name : row.reviewed_engagement_id;
  if (value) addField(panel, "Saved human decision", value);
  const reason = row[target + "_review_reason"];
  if (reason) addField(panel, "Saved reason", reason);
  return panel;
}

function reviewError(panel) {
  const error = element("p", "form-error");
  error.hidden = true;
  error.setAttribute("role", "alert");
  panel.append(error);
  return error;
}

function selectField(form, label, options, value = "") {
  const wrapper = element("label", "form-label", label);
  const select = element("select");
  for (const [optionValue, text] of options) {
    const option = element("option", "", text);
    option.value = optionValue;
    select.append(option);
  }
  select.value = value;
  wrapper.append(select);
  form.append(wrapper);
  return select;
}

function reasonField(form, value = "") {
  const wrapper = element("label", "form-label", "Reason (required)");
  const input = element("textarea");
  input.rows = 3;
  input.maxLength = 2000;
  input.required = true;
  input.value = value;
  wrapper.append(input);
  form.append(wrapper);
  return input;
}

function classificationPanel(row) {
  const panel = panelHeader(row, "classification", "1", "Classification", row.classification_complete);
  addField(panel, "Original model result", modelLabel(row));
  if (row.processing_status === "success") {
    addField(panel, "Attribution evidence strength", evidenceStrength(row.attribution_evidence_strength));
    addField(panel, "Model rationale", row.decision_rationale);
  }
  if (row.processing_status === "pending") {
    panel.append(element("p", "field-note", "Waiting for automatic classification before human review."));
    return panel;
  }
  if (row.processing_status === "failed") addField(panel, "Processing error", row.error);
  const canApprove = row.processing_status === "success" && ["HSBC", "SUPPLIER"].includes(row.classification);
  if (!canApprove) panel.append(element("p", "field-note", "Choose HSBC or Supplier with a reason to continue. UNCERTAIN keeps this incident at classification."));
  const error = reviewError(panel);
  const actions = element("div", "actions");
  const approve = button("Approved", () => saveReview(row, "classification", {decision: "approved"}, panel, error), "button primary");
  approve.disabled = !canApprove || row.classification_review_status === "approved";
  const form = element("form", "correction-form");
  form.hidden = true;
  const select = selectField(form, "Correct classification", [["", "Select a classification"], ["HSBC", "HSBC"], ["SUPPLIER", "Supplier"], ["UNCERTAIN", "Uncertain — keep unresolved"]], row.classification_review_status === "disagree" ? row.reviewed_classification : "");
  select.required = true;
  const reason = reasonField(form, row.classification_review_reason || "");
  const submit = element("button", "button primary", "Save human decision");
  submit.type = "submit";
  form.append(submit);
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!reason.value.trim()) { reason.setCustomValidity("Enter a reason."); reason.reportValidity(); return; }
    saveReview(row, "classification", {decision: "disagree", classification: select.value, reason: reason.value}, panel, error);
  });
  reason.addEventListener("input", () => reason.setCustomValidity(""));
  actions.append(approve, button("Disagree", () => { form.hidden = !form.hidden; if (!form.hidden) select.focus(); }));
  panel.append(actions, form, element("p", "field-note", "Saving another classification resets the later human decisions."));
  return panel;
}

function supplierPanel(row) {
  const panel = panelHeader(row, "supplier", "2", "Supplier name", row.supplier_complete && row.effective_classification === "SUPPLIER");
  addField(panel, "Model base name", row.supplier_name);
  if (!row.classification_complete || row.effective_classification !== "SUPPLIER") {
    const note = row.classification_complete && row.effective_classification === "HSBC"
      ? "HSBC needs no supplier or engagement review."
      : "Complete the classification as Supplier first.";
    panel.append(element("p", "field-note", note));
    return panel;
  }
  const error = reviewError(panel);
  const actions = element("div", "actions");
  const approve = button("Approved", () => saveReview(row, "supplier", {decision: "approved"}, panel, error), "button primary");
  approve.disabled = !usableModelSupplier(row) || row.supplier_review_status === "approved";
  const form = element("form", "correction-form");
  form.hidden = true;
  const options = [["", "Select a base supplier name"], ...supplierNames.map(name => [name, name])];
  const select = selectField(form, "Supplier catalog", options, row.supplier_review_status === "disagree" ? row.reviewed_supplier_name : "");
  select.required = true;
  select.disabled = !supplierNames.length;
  const reason = reasonField(form, row.supplier_review_reason || "");
  const submit = element("button", "button primary", "Save name and find engagements");
  submit.type = "submit";
  submit.disabled = !supplierNames.length;
  form.append(submit);
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!reason.value.trim()) { reason.setCustomValidity("Enter a reason."); reason.reportValidity(); return; }
    saveReview(row, "supplier", {decision: "disagree", supplier_name: select.value, reason: reason.value}, panel, error);
  });
  reason.addEventListener("input", () => reason.setCustomValidity(""));
  actions.append(approve, button("Disagree", () => { form.hidden = !form.hidden; if (!form.hidden) select.focus(); }));
  panel.append(actions, form, element("p", "field-note", "A changed base name reruns engagement finding now and resets engagement approval."));
  if (!supplierNames.length) panel.append(element("p", "notice", "No supplier catalog options are available. An existing usable model name can still be approved."));
  return panel;
}

function engagementPanel(row) {
  const complete = ["approved", "disagree"].includes(row.engagement_review_status) && Boolean(row.reviewed_engagement_id);
  const panel = panelHeader(row, "engagement", "3", "Engagement", complete);
  if (row.classification_complete && row.effective_classification === "HSBC") {
    panel.append(element("p", "field-note", "No engagement is needed for HSBC."));
    return panel;
  }
  const counts = element("div", "match-counts");
  for (const [label, value] of [["Name matches", row.link_match_count], ["LLM candidates", row.link_candidate_count], ["Suggestions", row.link_suggestion_count]]) {
    const item = element("div");
    item.append(element("strong", "", value === "" || value == null ? "—" : String(value)), element("span", "", label));
    counts.append(item);
  }
  panel.append(counts);
  addField(panel, "Automatic proposal status", row.link_status);
  if (row.link_supplier_name) addField(panel, "Base name used for search", row.link_supplier_name);
  if (row.link_reason) addField(panel, "Model recommendation", row.link_reason);
  if (row.link_error) addField(panel, "Finding error", row.link_error);
  const saved = {};
  for (const [key, value] of Object.entries(row)) {
    if (key.startsWith("ENG_") && value !== "") saved[key.slice(4)] = value;
  }
  if (Object.keys(saved).length) {
    const snapshot = engagementDetails(saved);
    snapshot.querySelector("summary").textContent = "Saved selected engagement details";
    panel.append(snapshot);
  }
  if (!row.classification_complete || !row.supplier_complete) panel.append(element("p", "notice", "Proposals can be inspected now. Approve classification and supplier name before deciding on an engagement."));
  const content = element("div", "engagement-content");
  content.append(element("p", "field-note", "Loading engagement matches…"));
  panel.append(content);
  queueMicrotask(() => loadEngagements(row, panel, content));
  return panel;
}

async function loadEngagements(row, panel, content) {
  try {
    const key = row.incident_id + ":" + row.review_version;
    let data = engagementCache.get(key);
    if (!data) {
      const response = await fetch("/api/incidents/" + encodeURIComponent(row.incident_id) + "/engagements", {cache: "no-store"});
      data = await response.json();
      if (!response.ok) throw new Error(apiError(data, "Could not load engagements."));
      engagementCache.set(key, data);
    }
    if (!content.isConnected) return;
    renderEngagements(row, data, panel, content);
  } catch (failure) {
    if (!content.isConnected) return;
    content.replaceChildren(element("p", "form-error", failure.message));
    content.append(button("Reload matches", () => loadEngagements(row, panel, content)));
  }
}

function engagementName(item) {
  return item.ENGAGEMENT_NAME || item.ENGAGEMENT_DESCRIPTION || item.THIRD_PARTY_NAME || item.THIRD_PARTY_NORMALISED_NAME || "Engagement";
}

function engagementDetails(item) {
  const details = disclosure("Engagement details");
  const fields = element("div", "source-grid");
  for (const [name, value] of Object.entries(item || {})) addField(fields, name, value);
  details.append(fields);
  return details;
}

function renderEngagements(row, data, panel, content) {
  content.replaceChildren();
  if (data.error) content.append(element("p", "notice", data.error));
  if (data.link_stale || data.review_version !== row.review_version) content.append(element("p", "notice", "The incident or catalog has changed. Refresh the page and find engagements again before approval."));
  const matches = data.matches || [];
  const suggestions = data.suggestions || [];
  const defaultId = data.selected_engagement_id || row.linked_engagement_id || "";
  addField(content, "Model default", defaultId || "No default selected");
  if (defaultId) {
    addField(content, "Default link evidence strength", evidenceStrength(row.link_confidence));
    content.append(element("p", "field-note", "A default is saved automatically. Human approval is a separate decision."));
  }
  const choices = disclosure("Model suggestions · " + suggestions.length + " of at most 5");
  choices.classList.add("suggestions");
  for (const suggestion of suggestions) {
    const item = element("article", "suggestion" + (suggestion.engagement_id === defaultId ? " default-suggestion" : ""));
    const title = suggestion.engagement_id + " · " + engagementName(suggestion.engagement || {});
    item.append(element("h4", "", title));
    if (suggestion.engagement_id === defaultId) item.append(element("span", "badge", "Model default"));
    item.append(element("p", "field-note", "Link evidence: " + evidenceStrength(suggestion.evidence_strength)));
    item.append(element("p", "record-text", suggestion.reason));
    item.append(engagementDetails(suggestion.engagement || {}));
    choices.append(item);
  }
  if (!suggestions.length) choices.append(element("p", "field-note", "No suitable engagement suggestion has been saved."));
  content.append(choices);
  const all = disclosure("Browse all " + matches.length + " normalized name matches");
  all.append(element("p", "field-note", "Source order. These name matches are not a relevance ranking. Only the capped candidates were prepared for the model."));
  for (const match of matches) {
    const item = disclosure(match.ENGAGEMENT_ID + " · " + engagementName(match));
    const fields = element("div", "source-grid");
    for (const [name, value] of Object.entries(match)) addField(fields, name, value);
    item.append(fields);
    all.append(item);
  }
  if (!matches.length) all.append(element("p", "field-note", "No matching engagement rows found."));
  content.append(all);
  const error = reviewError(content);
  const allowed = row.classification_complete && row.supplier_complete && row.effective_classification === "SUPPLIER";
  if (!allowed) return;
  const current = !data.link_stale && data.review_version === row.review_version;
  const form = element("form", "correction-form");
  const options = [["", "None of these engagements"], ...matches.map(item => [item.ENGAGEMENT_ID, item.ENGAGEMENT_ID + " · " + engagementName(item)])];
  const hasHumanDecision = ["approved", "disagree"].includes(row.engagement_review_status);
  const selected = hasHumanDecision ? (row.reviewed_engagement_id || "") : defaultId;
  const select = selectField(form, "Engagement choice (all name matches)", options, selected);
  select.disabled = !current;
  const reasonArea = element("div");
  reasonArea.hidden = true;
  const reason = reasonField(reasonArea, row.engagement_review_reason || "");
  const save = element("button", "button primary", "Save engagement decision");
  save.type = "submit";
  save.disabled = !current;
  reasonArea.append(save);
  const actions = element("div", "actions");
  const approve = button("Approved", () => saveReview(row, "engagement", {decision: "approved", engagement_id: defaultId}, panel, error), "button primary");
  function updateChoice() {
    approve.disabled = !current || !defaultId || select.value !== defaultId || row.engagement_review_status === "approved";
    if (select.value !== defaultId) reasonArea.hidden = false;
  }
  select.addEventListener("change", updateChoice);
  const disagree = button("Disagree", () => { reasonArea.hidden = !reasonArea.hidden; if (!reasonArea.hidden) reason.focus(); });
  disagree.disabled = !current;
  actions.append(approve, disagree);
  form.append(actions, reasonArea);
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!reason.value.trim()) { reason.setCustomValidity("Enter a reason."); reason.reportValidity(); return; }
    saveReview(row, "engagement", {decision: "disagree", engagement_id: select.value, reason: reason.value}, panel, error);
  });
  reason.addEventListener("input", () => reason.setCustomValidity(""));
  updateChoice();
  content.append(form);
  const retryLabel = row.link_status === "RUNNING" ? "Restart engagement finding" : "Find engagements again";
  const retry = button(retryLabel, () => saveRequest(row, "engagement", "/api/incidents/" + encodeURIComponent(row.incident_id) + "/refresh-links", {version: row.review_version}, panel, error));
  content.append(retry, element("p", "field-note", "Finding again replaces proposals and resets engagement approval. Selecting another match or none requires a reason."));
}

function modelDetails(row) {
  const details = disclosure("Model evidence and supplier details");
  const fields = element("div", "source-grid");
  addField(fields, "Processing status", row.processing_status);
  addField(fields, "Key root cause", row.key_root_cause);
  const evidence = Array.isArray(row.evidence_column) ? row.evidence_column.join(", ") : row.evidence_column;
  addField(fields, "Evidence columns", evidence);
  if (row.classification === "SUPPLIER") {
    for (const [label, value] of [["Supplier base name", row.supplier_name], ["Product or service", row.supplier_product_or_service], ["Supplier action or failure", row.supplier_action_or_failure], ["Causal explanation", row.supplier_causal_explanation], ["Accountability reason", row.supplier_accountability_reason], ["Additional supplier information", row.supplier_more_info]]) addField(fields, label, value);
  }
  details.append(fields);
  return details;
}

function inputDetails(row) {
  const details = disclosure("Original incident fields");
  const fields = element("div", "source-grid");
  for (const item of sourceFields(row)) addField(fields, item.name, item.value);
  details.append(fields);
  return details;
}

function renderRecords() {
  const query = $("search").value.trim().toLowerCase();
  const reviewFilter = $("review-filter").value;
  const visible = records.filter(row => {
    if (activeFilter === "failed" || activeFilter === "pending") {
      if (row.processing_status !== activeFilter) return false;
    } else if (activeFilter !== "total" && (row.processing_status !== "success" || row.classification !== activeFilter)) return false;
    if (reviewFilter === "pending" && row.review_complete) return false;
    if (reviewFilter === "complete" && !row.review_complete) return false;
    const searchText = [row.incident_id, incidentTitle(row), row.supplier_name, row.effective_supplier_name, row.classification, row.linked_engagement_id, row.reviewed_engagement_id].join(" ").toLowerCase();
    return !query || searchText.includes(query);
  });
  let label = "All incidents";
  for (const control of document.querySelectorAll("[data-filter]")) {
    const selected = control.dataset.filter === activeFilter;
    control.setAttribute("aria-pressed", String(selected));
    if (selected) label = control.querySelector("span").textContent;
  }
  $("results-heading").textContent = label;
  $("filter-summary").textContent = visible.length + " of " + records.length + " incidents shown";
  $("dashboard-empty").hidden = visible.length > 0;
  $("dashboard-empty").textContent = "No incidents match " + label.toLowerCase() + " and the selected search or review filter.";
  $("incident-list").replaceChildren(...visible.map(recordCard));
}

function showDashboard(data) {
  records = data.incidents || [];
  supplierNames = data.supplier_names || [];
  engagementCache.clear();
  $("mode").textContent = data.demo ? "Synthetic demonstration" : "Incident review";
  $("demo-note").hidden = !data.demo;
  for (const key of ["total", "HSBC", "SUPPLIER", "UNCERTAIN", "failed", "pending"]) $(key + "-count").textContent = data.counts[key] ?? 0;
  $("review-complete-count").textContent = data.counts.review_complete ?? 0;
  $("review-pending-count").textContent = data.counts.review_pending ?? 0;
  $("human-linked-count").textContent = data.counts.human_linked ?? 0;
  $("review-progress").max = Math.max(1, data.counts.total || 0);
  $("review-progress").value = data.counts.review_complete || 0;
  for (const [id, value] of [["supplier-catalog-note", data.supplier_catalog_note], ["engagement-catalog-note", data.engagement_catalog_note]]) {
    $(id).textContent = value || "";
    $(id).hidden = !value;
  }
  renderRecords();
}

function apiError(data, fallback) {
  if (typeof data.detail === "string") return data.detail;
  if (typeof data.error === "string" && data.error) return data.error;
  return fallback;
}

function lockControls() {
  const controls = [...document.querySelectorAll("button, input, select, textarea")];
  const states = controls.map(control => control.disabled);
  for (const control of controls) control.disabled = true;
  return () => controls.forEach((control, index) => { control.disabled = states[index]; });
}

function saveReview(row, target, decision, panel, error) {
  const payload = {incident_id: row.incident_id, version: row.review_version, target, ...decision};
  return saveRequest(row, target, "/api/review", payload, panel, error);
}

async function saveRequest(row, target, url, payload, panel, error) {
  if (busy) return;
  busy = true;
  const unlock = lockControls();
  error.hidden = true;
  panel.setAttribute("aria-busy", "true");
  $("message").className = "message";
  $("message").textContent = target === "supplier" || url.endsWith("refresh-links") ? "Saving and finding engagements… Please wait for the saved result." : "Saving human decision…";
  $("message").hidden = false;
  try {
    const response = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(apiError(data, "Could not save. Refresh and try again."));
    showDashboard(data);
    const saved = records.find(item => item.incident_id === row.incident_id);
    const failedFinding = saved && saved.link_status === "FAILED" && (target === "supplier" || url.endsWith("refresh-links"));
    $("message").textContent = failedFinding
      ? "Decision saved, but engagement finding failed. Review the error and use Find engagements again to retry."
      : "Decision saved. Review status and engagement proposals have been refreshed.";
    const card = [...document.querySelectorAll(".incident-card")].find(item => item.dataset.incidentId === row.incident_id);
    const savedPanel = card && card.querySelector('[data-review-target="' + target + '"]');
    if (savedPanel) savedPanel.focus({preventScroll: true});
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
    $("message").className = "message error";
    $("message").textContent = failure.message;
  } finally {
    busy = false;
    panel.removeAttribute("aria-busy");
    unlock();
  }
}

async function loadDashboard() {
  if (busy) return;
  busy = true;
  const unlock = lockControls();
  $("message").hidden = true;
  try {
    const response = await fetch("/api/dashboard", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(apiError(data, "Could not load incidents."));
    showDashboard(data);
  } catch (failure) {
    $("message").textContent = failure.message;
    $("message").className = "message error";
    $("message").hidden = false;
  } finally {
    busy = false;
    unlock();
  }
}

for (const control of document.querySelectorAll("[data-filter]")) {
  control.addEventListener("click", () => { activeFilter = control.dataset.filter; renderRecords(); });
}
$("search").addEventListener("input", renderRecords);
$("review-filter").addEventListener("change", renderRecords);
$("reload").addEventListener("click", loadDashboard);
window.addEventListener("hashchange", () => { expandedId = readHash(); renderRecords(); });
loadDashboard();
