const $ = id => document.getElementById(id);
let records = [];
let supplierCatalogCount = 0;
let supplierCountries = [];
let activeFilter = "total";
let expandedId = readHash();
let busy = false;
const engagementCache = new Map();

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
  return field;
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

function incidentTitle(row) {
  const values = row.input_fields;
  for (const name of ["SHORT_DESCRIPTION", "INCIDENT_SHORT_DESCRIPTION", "INCIDENT_DESCRIPTION", "IT_PROBLEM_DESCRIPTION"]) {
    const field = values.find(item => item.name === name && item.value);
    if (field) return String(field.value);
  }
  return row.key_root_cause || "Incident details";
}


function focusSection(section) {
  section.focus({preventScroll: true});
  const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
  section.scrollIntoView({behavior, block: "center"});
}

function nextActionCard(row, steps) {
  const action = row.next_action;
  const card = element("section", "next-action");
  card.append(element("h3", "", "Next step · " + action.title));
  card.append(element("p", "field-note", action.description));
  if (["classification", "supplier", "engagement"].includes(action.stage)) {
    card.append(button("Go to " + action.stage + " review", () => {
      const panel = steps.querySelector('[data-review-target="' + action.stage + '"]');
      if (panel) focusSection(panel);
    }));
  }
  return card;
}

function comparisonHeader(table, labels) {
  const head = element("thead");
  const row = element("tr");
  for (const label of labels) {
    const cell = element("th", "", label);
    cell.scope = "col";
    row.append(cell);
  }
  head.append(row);
  table.append(head);
}

function decisionComparison(row) {
  const details = disclosure("AI proposal vs human decision");
  details.classList.add("decision-comparison");
  details.append(element("p", "field-note", "Current saved decisions. The engagement proposal reflects the latest search, not a history of earlier proposals."));
  const wrapper = element("div", "table-scroll");
  wrapper.tabIndex = 0;
  wrapper.setAttribute("role", "region");
  wrapper.setAttribute("aria-label", "Compare AI and human decisions");
  const table = element("table", "comparison-table");
  table.append(element("caption", "", "Three decisions for this incident"));
  comparisonHeader(table, ["Step", "AI proposal", "Human decision", "Recorded reason"]);
  const body = element("tbody");
  const steps = [
    ["classification", "Classification", modelLabel(row), row.reviewed_classification],
    ["supplier", "Supplier name", row.supplier_name, row.reviewed_supplier_name],
    ["engagement", "Engagement", row.linked_engagement_id, row.reviewed_engagement_id]
  ];
  for (const [target, label, proposed, reviewed] of steps) {
    const status = row[target + "_review_status"];
    const decided = ["approved", "disagree"].includes(status);
    let human = "Pending review";
    if (status === "not_applicable") human = "Not applicable";
    if (decided) human = reviewed || (target === "engagement" ? "None of these — review complete" : "Not recorded");
    if (target === "classification" && reviewed === "UNCERTAIN") human += " — unresolved";
    if (status === "approved") human += " · Approved";
    if (status === "disagree" && reviewed) human += " · Reviewer choice";
    const changed = decided && (proposed || "") !== (reviewed || "");
    const line = element("tr", changed ? "changed" : "");
    const heading = element("th", "", label);
    heading.scope = "row";
    line.append(heading, element("td", "", proposed || "No proposal"), element("td", "", human));
    line.append(element("td", "", row[target + "_review_reason"] || (status === "approved" ? "Approved without correction." : "—")));
    body.append(line);
  }
  table.append(body);
  wrapper.append(table);
  details.append(wrapper);
  return details;
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
    const insights = element("div", "engagement-insights");
    const sources = inputDetails(row);
    const citations = splitCitations(row.citations);
    steps.append(classificationPanel(row), supplierPanel(row), engagementPanel(row, insights));
    body.append(nextActionCard(row, steps), decisionComparison(row), steps,
      classificationDetails(row, sources, citations), linkingDetails(row, citations), sources);
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
    badge.textContent = "Review complete · no link";
    badge.className = "badge";
  }
  if (target === "engagement" && row.engagement_review_status === "pending") {
    badge.textContent = row.supplier_complete ? "Awaiting your approval" : "Waiting for earlier reviews";
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
  input.addEventListener("input", () => input.setCustomValidity(""));
  wrapper.append(input);
  form.append(wrapper);
  return input;
}

function requireReason(input) {
  if (input.value.trim()) return true;
  input.setCustomValidity("Enter a reason.");
  input.reportValidity();
  return false;
}

function classificationPanel(row) {
  const panel = panelHeader(row, "classification", "1", "Classification", row.classification_complete);
  addField(panel, "Original model result", modelLabel(row));
  if (row.processing_status === "success") {
    addField(panel, "Attribution evidence strength", evidenceStrength(row.attribution_evidence_strength));
    addField(panel, "Model rationale", row.decision_rationale);
    const context = disclosure("Countries and incident roles · model extraction");
    const facts = element("div", "source-grid");
    for (const [label, value] of [
      ["Incident country", row.incident_country],
      ["Supplier country", row.supplier_country],
      ["Causing party", row.causing_party],
      ["Affected party", row.affected_party],
      ["Resolving party", row.resolving_party]
    ]) addField(facts, label, value);
    context.append(facts, element("p", "field-note", "Model-extracted facts, not independently verified. The affected party and the party restoring service are not necessarily responsible. Missing facts stay unrecorded."));
    panel.append(context);
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
  const approve = button(row.classification_review_status === "approved" ? "Approved" : "Approve classification", () => saveReview(row, "classification", {decision: "approved"}, panel, error), "button primary");
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
    if (!requireReason(reason)) return;
    saveReview(row, "classification", {decision: "disagree", classification: select.value, reason: reason.value}, panel, error);
  });
  actions.append(approve, button("Disagree", () => { form.hidden = !form.hidden; if (!form.hidden) select.focus(); }));
  panel.append(actions, form, element("p", "field-note", "Saving another classification resets the later human decisions."));
  return panel;
}

function supplierPanel(row) {
  const panel = panelHeader(row, "supplier", "2", "Supplier name", row.supplier_complete && row.effective_classification === "SUPPLIER");
  addField(panel, "Model base name", row.supplier_name);
  if (row.classification === "SUPPLIER") addField(panel, "Model supplier country", row.supplier_country);
  if (!row.classification_complete || row.effective_classification !== "SUPPLIER") {
    const note = row.classification_complete && row.effective_classification === "HSBC"
      ? "HSBC needs no supplier or engagement review."
      : "Complete the classification as Supplier first.";
    panel.append(element("p", "field-note", note));
    return panel;
  }
  const error = reviewError(panel);
  const actions = element("div", "actions");
  const approve = button(row.supplier_review_status === "approved" ? "Approved" : "Approve supplier", () => saveReview(row, "supplier", {decision: "approved"}, panel, error), "button primary");
  approve.disabled = !usableModelSupplier(row) || row.supplier_review_status === "approved";
  const form = element("form", "correction-form");
  form.hidden = true;
  const initialName = row.supplier_review_status === "disagree" ? row.reviewed_supplier_name : "";
  const picker = supplierPicker(form, initialName);
  const reason = reasonField(form, row.supplier_review_reason || "");
  const submit = element("button", "button primary", "Save name and find engagements");
  submit.type = "submit";
  submit.disabled = !supplierCatalogCount;
  form.append(submit);
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!requireReason(reason)) return;
    saveReview(row, "supplier", {decision: "disagree", supplier_name: picker.select.value, reason: reason.value}, panel, error);
  });
  actions.append(approve, button("Change supplier", () => {
    form.hidden = !form.hidden;
    if (!form.hidden) {
      picker.open();
      picker.search.focus();
    }
  }));
  panel.append(actions, form, element("p", "field-note", "A changed base name reruns engagement finding now and resets engagement approval."));
  if (!supplierCatalogCount) panel.append(element("p", "notice", "No supplier catalog options are available. An existing usable model name can still be approved."));
  return panel;
}

function supplierPicker(form, initialName) {
  const wrapper = element("div", "supplier-picker");
  const filters = element("div", "supplier-search-filters");
  const label = element("label", "form-label", "Search " + supplierCatalogCount.toLocaleString() + " supplier names");
  const search = element("input");
  search.type = "search";
  search.placeholder = "Type part of a supplier name…";
  search.maxLength = 200;
  search.autocomplete = "off";
  label.append(search);
  filters.append(label);
  const countryOptions = [["", "All countries"], ...supplierCountries.map(name => [name, name])];
  const country = selectField(filters, "Catalog country (optional)", countryOptions);
  country.disabled = !supplierCountries.length;
  wrapper.append(filters);
  wrapper.append(element("p", "field-note", "Country narrows this name list only. It is not the incident location or an engagement restriction. Use All countries to include suppliers without a recorded country."));
  const select = selectField(wrapper, "Supplier catalog", [["", "Select a supplier name"]]);
  select.required = true;
  select.disabled = !supplierCatalogCount;
  const selected = element("p", "supplier-selection");
  const status = element("p", "field-note supplier-search-status");
  status.setAttribute("role", "status");
  const pagination = element("div", "supplier-pagination");
  const previous = button("Previous 50", () => loadOptions(Math.max(0, offset - 50)));
  const next = button("Next 50", () => loadOptions(offset + 50));
  previous.disabled = true;
  next.disabled = true;
  pagination.append(previous, next);
  wrapper.append(selected, status, pagination);
  form.append(wrapper);

  let selectedName = initialName;
  let offset = 0;
  let controller;
  let timer;

  function showOptions(options) {
    select.replaceChildren();
    const placeholder = element("option", "", "Select a supplier name");
    placeholder.value = "";
    select.append(placeholder);
    for (const supplier of options) {
      const countries = supplier.countries.length ? supplier.countries.join(", ") : "Country not recorded";
      const option = element("option", "", supplier.name + " · " + countries);
      option.value = supplier.name;
      select.append(option);
    }
    if (selectedName && !options.some(item => item.name === selectedName)) {
      const current = element("option", "", selectedName + " · current selection, outside this page/filter");
      current.value = selectedName;
      select.append(current);
    }
    select.value = selectedName;
    selected.textContent = selectedName ? "Selected supplier: " + selectedName : "No replacement selected. Choose a name and give a reason below.";
  }

  async function loadOptions(start) {
    if (!wrapper.isConnected) return;
    if (busy) {
      status.textContent = "Wait for the current save, then press Enter in the search field to retry.";
      return;
    }
    clearTimeout(timer);
    if (controller) controller.abort();
    const request = new AbortController();
    controller = request;
    previous.disabled = true;
    next.disabled = true;
    status.className = "field-note supplier-search-status";
    status.textContent = "Searching the supplier catalog…";
    showOptions([]);
    const params = new URLSearchParams({q: search.value, country: country.value, offset: String(start)});
    try {
      const response = await fetch("/api/suppliers?" + params, {signal: request.signal, cache: "no-store"});
      const data = await response.json();
      if (!response.ok) throw new Error(apiError(data, "Could not search suppliers. Try again."));
      if (request.signal.aborted || !wrapper.isConnected) return;
      if (start > 0 && !data.suppliers.length) return loadOptions(0);
      offset = data.offset;
      showOptions(data.suppliers);
      status.textContent = data.total
        ? "Showing " + (offset + 1) + "–" + (offset + data.suppliers.length) + " of " + data.total.toLocaleString() + " matching names. Search keeps your selected name."
        : "No matching names. Clear the search or choose All countries. Your selected name is kept.";
      previous.disabled = busy || offset === 0;
      next.disabled = busy || !data.has_more;
    } catch (failure) {
      if (request.signal.aborted || !wrapper.isConnected) return;
      status.className = "form-error supplier-search-status";
      status.textContent = failure.message;
    }
  }

  search.addEventListener("input", () => {
    clearTimeout(timer);
    if (controller) controller.abort();
    showOptions([]);
    previous.disabled = true;
    next.disabled = true;
    status.textContent = "Searching the supplier catalog…";
    timer = setTimeout(() => loadOptions(0), 250);
  });
  search.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadOptions(0);
    }
  });
  country.addEventListener("change", () => loadOptions(0));
  select.addEventListener("change", () => {
    selectedName = select.value;
    selected.textContent = selectedName ? "Selected supplier: " + selectedName : "No replacement selected. Choose a name and give a reason below.";
  });
  showOptions([]);
  return {select, search, open() { loadOptions(0); }};
}

function engagementPanel(row, insights) {
  const accepted = ["approved", "disagree"].includes(row.engagement_review_status) && Boolean(row.reviewed_engagement_id);
  const panel = panelHeader(row, "engagement", "3", "Engagement", accepted);
  if (row.classification_complete && row.effective_classification === "HSBC") {
    panel.append(element("p", "field-note", "No engagement is needed for HSBC."));
    return panel;
  }

  const counts = element("div", "match-counts");
  for (const [label, value] of [["Name matches", row.link_match_count], ["LLM candidates", row.link_candidate_count], ["Model suggestions", row.link_suggestion_count]]) {
    const item = element("div");
    const count = value === "" || value == null ? "—" : String(value);
    item.append(element("strong", "", count), element("span", "", label));
    counts.append(item);
  }
  panel.append(counts);
  if (!row.classification_complete || !row.supplier_complete) {
    panel.append(element("p", "notice", "Inspect the proposals now. Complete classification and supplier-name review before choosing an engagement."));
  }

  const content = element("div", "engagement-content");
  content.append(element("p", "field-note", "Loading engagement matches…"));
  panel.append(content, insights);
  queueMicrotask(() => loadEngagements(row, panel, content, insights));
  return panel;
}

async function loadEngagements(row, panel, content, insights) {
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
    insights.replaceChildren(engagementComparison(row, data), matchingExplanation(data));
  } catch (failure) {
    if (!content.isConnected) return;
    content.replaceChildren(element("p", "form-error", failure.message));
    content.append(button("Reload matches", () => loadEngagements(row, panel, content, insights)));
  }
}

function engagementName(item) {
  return item.ENGAGEMENT_NAME || item.ENGAGEMENT_DESCRIPTION_TEXT || item.ENGAGEMENT_DESCRIPTION || item.THIRD_PARTY_NAME || item.THIRD_PARTY_NORMALISED_NAME || "Engagement";
}

function engagementDetails(item, title = "Engagement details") {
  const details = disclosure(title);
  const fields = element("div", "source-grid");
  for (const [name, value] of Object.entries(item)) addField(fields, name, value);
  details.append(fields);
  return details;
}

function engagementPicker(container, matches, selectedId, enabled) {
  const picker = element("div", "engagement-picker");
  const searchLabel = element("label", "picker-search", "Search all " + matches.length + " matching engagements");
  const search = element("input");
  search.type = "search";
  search.placeholder = "Engagement ID, supplier or service";
  search.autocomplete = "off";
  searchLabel.append(search);
  const select = selectField(picker, "Engagement choice · all " + matches.length + " matches", [], "");
  select.parentElement.classList.add("picker-select");
  select.disabled = !enabled;
  const results = element("p", "picker-results field-note");
  results.setAttribute("role", "status");
  results.setAttribute("aria-live", "polite");
  picker.prepend(searchLabel);
  picker.append(results);
  container.append(picker);
  let currentId = selectedId;

  function renderOptions() {
    const query = search.value.trim().toLowerCase();
    const visible = [];
    for (const match of matches) {
      const text = [match.ENGAGEMENT_ID, match.THIRD_PARTY_NAME, match.THIRD_PARTY_NORMALISED_NAME,
        match.ENGAGEMENT_NAME, match.ENGAGEMENT_DESCRIPTION_TEXT, match.ENGAGEMENT_DESCRIPTION,
        match.SERVICE_CATEGORY_L1_NAME].join(" ").toLowerCase();
      if (!query || text.includes(query)) visible.push(match);
    }
    const options = [["", "None of these engagements"]];
    for (const match of visible) options.push([match.ENGAGEMENT_ID, match.ENGAGEMENT_ID + " · " + engagementName(match)]);
    const selectionVisible = options.some(option => option[0] === currentId);
    if (currentId && !selectionVisible) {
      const selected = matches.find(match => match.ENGAGEMENT_ID === currentId);
      const name = selected ? engagementName(selected) : "Unavailable in the current catalog";
      options.push([currentId, currentId + " · " + name + " · Current selection"]);
    }
    select.replaceChildren();
    for (const [value, label] of options) {
      const option = element("option", "", label);
      option.value = value;
      select.append(option);
    }
    select.value = currentId;
    results.textContent = visible.length + " of " + matches.length + " matches shown. Search keeps the current selection.";
  }

  search.addEventListener("input", renderOptions);
  search.addEventListener("keydown", event => {
    if (event.key === "Enter") event.preventDefault();
  });
  select.addEventListener("change", () => { currentId = select.value; });
  renderOptions();
  return {
    select,
    setValue(value) {
      currentId = value;
      renderOptions();
    }
  };
}

function engagementSuggestionCards(row, data, selectedId, enabled, choose) {
  const grid = element("div", "suggestion-grid");
  grid.setAttribute("role", "radiogroup");
  grid.setAttribute("aria-label", "Suggested engagements");
  for (const suggestion of data.suggestions) {
    const isDefault = suggestion.engagement_id === data.selected_engagement_id;
    const card = element("article", "suggestion" + (isDefault ? " default-suggestion" : ""));
    card.dataset.engagementId = suggestion.engagement_id;
    card.dataset.strength = String(suggestion.evidence_strength);
    const label = element("label", "suggestion-choice");
    const radio = element("input");
    radio.type = "radio";
    radio.name = "suggested-engagement-" + row.incident_id;
    radio.value = suggestion.engagement_id;
    radio.checked = radio.value === selectedId;
    radio.disabled = !enabled;
    radio.addEventListener("change", () => choose(radio.value));
    const title = element("span");
    title.append(element("strong", "", suggestion.engagement_id));
    title.append(element("span", "", engagementName(suggestion.engagement)));
    label.append(radio, title);
    card.append(label);
    if (isDefault) card.append(element("span", "badge", "Model default"));
    card.append(element("p", "suggestion-score", evidenceStrength(suggestion.evidence_strength)));
    card.append(element("p", "suggestion-reason", suggestion.reason));
    card.append(engagementDetails(suggestion.engagement));
    card.classList.toggle("is-selected", radio.checked);
    grid.append(card);
  }
  if (!data.suggestions.length) grid.append(element("p", "field-note", "No supported model suggestion is saved. Inspect the matching catalog rows below."));
  return grid;
}

function renderEngagements(row, data, panel, content) {
  content.replaceChildren();
  if (data.error) content.append(element("p", "notice", data.error));
  const fresh = !data.link_stale && data.review_version === row.review_version;
  const reviewedSupplier = row.classification_complete && row.supplier_complete && row.effective_classification === "SUPPLIER";
  const currentSupplier = row.link_supplier_name === row.reviewed_supplier_name;
  const canReview = fresh && reviewedSupplier && currentSupplier && Boolean(row.link_catalog_hash) && row.link_status !== "RUNNING";
  if (!fresh) content.append(element("p", "notice", "The incident or catalog changed. Refresh the page and find engagements again before approval."));
  if (row.link_status === "RUNNING") content.append(element("p", "notice", "Engagement finding is running. Wait for it to finish or explicitly restart it."));
  if (reviewedSupplier && (!currentSupplier || !row.link_catalog_hash)) {
    content.append(element("p", "notice", "Find engagements for the reviewed supplier before saving a decision."));
  }

  const defaultId = data.selected_engagement_id || "";
  const hasHumanDecision = ["approved", "disagree"].includes(row.engagement_review_status);
  const selectedId = hasHumanDecision ? (row.reviewed_engagement_id || "") : defaultId;
  const form = element("form", "engagement-decision");
  const picker = engagementPicker(form, data.matches, selectedId, canReview);
  const reasonArea = element("div", "reason-area");
  const reason = reasonField(reasonArea, row.engagement_review_reason || "");
  reason.disabled = !canReview;
  const state = element("p", "decision-state");
  const error = reviewError(form);
  const actions = element("div", "decision-actions actions");
  let explicitDisagreement = false;

  function choose(id) {
    if (!canReview || busy) return;
    picker.setValue(id);
    explicitDisagreement = false;
    updateChoice();
  }

  const choices = element("section", "suggestions");
  const heading = element("div", "suggestions-heading");
  heading.append(element("h3", "", "Suggested engagements · " + data.suggestions.length));
  heading.append(button("Compare", () => {
    const comparison = panel.querySelector(".engagement-comparison");
    if (comparison) {
      comparison.open = true;
      focusSection(comparison.querySelector("summary"));
    }
  }));
  const cards = engagementSuggestionCards(row, data, selectedId, canReview, choose);
  choices.append(heading, cards);
  choices.append(element("p", "evidence-legend", "Green intensity shows model evidence strength, not approval. Equal scores have the same color."));
  content.append(choices);

  const approve = button("", () => {
    if (!canReview || picker.select.value !== defaultId || !defaultId) return;
    saveReview(row, "engagement", {decision: "approved", engagement_id: defaultId}, panel, error);
  }, "button primary");
  const disagree = button("Disagree", () => {
    explicitDisagreement = true;
    updateChoice();
    reason.focus();
  });
  const none = button("None of these", () => {
    choose("");
    reason.focus();
  });
  disagree.disabled = !canReview;
  none.disabled = !canReview;
  const save = element("button", "button primary", "Save engagement decision");
  save.type = "submit";
  save.disabled = !canReview;
  actions.append(none, disagree, approve, save);
  form.append(state, reasonArea, actions);
  form.append(element("p", "field-note", "A different selection or no link requires a reason. Choosing a card or dropdown option does not save a decision."));

  function updateChoice() {
    const selected = picker.select.value;
    const needsReason = explicitDisagreement || !defaultId || selected !== defaultId;
    reasonArea.hidden = !needsReason;
    reason.required = needsReason;
    save.hidden = !needsReason;
    approve.hidden = needsReason;
    approve.textContent = row.engagement_review_status === "approved" ? "Approved " + defaultId : "Approve " + defaultId;
    approve.disabled = !canReview || !defaultId || selected !== defaultId || row.engagement_review_status === "approved";
    for (const radio of cards.querySelectorAll("input[type=radio]")) {
      radio.checked = radio.value === selected;
      radio.closest(".suggestion").classList.toggle("is-selected", radio.checked);
    }
    const sameSavedChoice = hasHumanDecision && selected === (row.reviewed_engagement_id || "") && !explicitDisagreement;
    state.classList.toggle("confirmed", canReview && sameSavedChoice && Boolean(selected));
    if (!canReview) state.textContent = "Engagement decisions are locked until the earlier reviews and current lookup are ready.";
    else if (sameSavedChoice) {
      state.textContent = selected ? "Saved human choice: " + selected : "Saved review: no engagement accepted.";
    } else {
      state.textContent = selected ? "Selected proposal: " + selected + " · Human approval pending" : "No engagement selected · Save a reason to complete review without a link.";
    }
  }

  picker.select.addEventListener("change", () => {
    explicitDisagreement = false;
    updateChoice();
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!canReview || reasonArea.hidden || !requireReason(reason)) return;
    saveReview(row, "engagement", {decision: "disagree", engagement_id: picker.select.value, reason: reason.value}, panel, error);
  });
  updateChoice();
  content.append(form);

  const all = disclosure("Browse all " + data.matches.length + " matching engagement records");
  all.append(element("p", "field-note", "Source order, not relevance ranking. Only the capped candidates were prepared for the model."));
  for (const match of data.matches) {
    all.append(engagementDetails(match, match.ENGAGEMENT_ID + " · " + engagementName(match)));
  }
  if (!data.matches.length) all.append(element("p", "field-note", "No matching catalog rows."));
  content.append(all);
  if (reviewedSupplier) {
    const retryLabel = row.link_status === "RUNNING" ? "Restart engagement finding" : "Find engagements again";
    content.append(button(retryLabel, () => saveRequest(row, "engagement", "/api/incidents/" + encodeURIComponent(row.incident_id) + "/refresh-links", {version: row.review_version}, panel, error)));
    content.append(element("p", "field-note", "Finding again replaces proposals and resets engagement approval."));
  }
}

function matchingExplanation(data) {
  const details = disclosure("How did Python find these names?");
  details.classList.add("matching-explanation");
  const explanation = data.matching_explanation;
  addField(details, "Supplier base name", explanation.supplier_name);
  addField(details, "Normalized for matching", explanation.normalized_supplier_name);
  details.append(element("p", "field-note", "Lowercase, ASCII folding and word spacing. THIRD_PARTY_NAME is checked before THIRD_PARTY_NORMALISED_NAME. Matches stay in source order; similarity is not proof of a link."));
  const list = element("div", "matching-list");
  for (const match of explanation.matches) {
    const item = disclosure(match.engagement_id + " · " + match.source_name);
    addField(item, "Matching source column", match.column);
    addField(item, "Original catalog name", match.source_name);
    addField(item, "Normalized catalog name", match.normalized_name);
    addField(item, "Python matching rule", match.method);
    list.append(item);
  }
  if (!explanation.matches.length) list.append(element("p", "field-note", "No matching catalog rows for this name."));
  details.append(list);
  return details;
}

function defaultComparisonIds(data) {
  const preferred = [data.selected_engagement_id, data.reviewed_engagement_id];
  for (const suggestion of data.suggestions) preferred.push(suggestion.engagement_id);
  for (const match of data.matches) preferred.push(match.ENGAGEMENT_ID);

  const availableIds = new Set(data.matches.map(match => match.ENGAGEMENT_ID));
  const selectedIds = [];
  for (const id of preferred) {
    if (availableIds.has(id) && !selectedIds.includes(id)) selectedIds.push(id);
  }
  return selectedIds;
}

function engagementComparison(row, data) {
  const details = disclosure("Compare engagements side by side");
  details.classList.add("engagement-comparison");
  details.append(element("p", "field-note", "Compare up to three of all current Python matches. Highlighted differences describe catalog values, not which engagement is correct. Comparison choices do not save a decision."));
  if (data.link_stale || data.review_version !== row.review_version) details.append(element("p", "notice", "The incident or catalog changed. This comparison may be newer than the displayed decision. Refresh the page and suggestions before deciding."));
  if (!data.matches.length) {
    details.append(element("p", "field-note", "No matching engagements to compare."));
    return details;
  }
  const controls = element("div", "comparison-controls");
  const comparisonSelects = [];
  const initialIds = defaultComparisonIds(data);
  const options = [["", "No comparison column"], ...data.matches.map(item => [item.ENGAGEMENT_ID, item.ENGAGEMENT_ID + " · " + engagementName(item)])];
  for (let index = 0; index < Math.min(3, data.matches.length); index++) {
    const select = selectField(controls, "Compare option " + (index + 1), options, initialIds[index] || "");
    comparisonSelects.push(select);
  }
  const toggleLabel = element("label", "difference-toggle");
  const differencesOnly = element("input");
  differencesOnly.type = "checkbox";
  differencesOnly.checked = true;
  toggleLabel.append(differencesOnly, document.createTextNode(" Show catalog differences only"));
  controls.append(toggleLabel);
  const wrapper = element("div", "table-scroll");
  wrapper.tabIndex = 0;
  wrapper.setAttribute("role", "region");
  wrapper.setAttribute("aria-label", "Engagement comparison table");
  details.append(controls, wrapper);
  function updateComparison() {
    const selectedIds = [];
    for (const select of comparisonSelects) {
      const id = select.value;
      if (id && !selectedIds.includes(id)) selectedIds.push(id);
    }
    const matches = selectedIds.map(id => data.matches.find(match => match.ENGAGEMENT_ID === id));
    renderEngagementComparison(wrapper, data, matches, differencesOnly.checked);
  }

  for (const select of comparisonSelects) select.addEventListener("change", updateComparison);
  differencesOnly.addEventListener("change", updateComparison);
  updateComparison();
  return details;
}

function renderEngagementComparison(wrapper, data, matches, differencesOnly) {
  wrapper.replaceChildren();
  if (!matches.length) {
    wrapper.append(element("p", "field-note", "Select an engagement to inspect."));
    return;
  }
  const table = element("table", "comparison-table");
  table.append(element("caption", "", "Current engagement catalog · " + matches.length + " distinct selections"));
  const labels = ["Field"];
  for (const match of matches) {
    let label = match.ENGAGEMENT_ID + " · " + engagementName(match);
    if (match.ENGAGEMENT_ID === data.selected_engagement_id) label += " · Model default";
    if (match.ENGAGEMENT_ID === data.reviewed_engagement_id) label += " · Human choice";
    labels.push(label);
  }
  comparisonHeader(table, labels);
  const body = element("tbody");
  const suggestions = matches.map(match => data.suggestions.find(item => item.engagement_id === match.ENGAGEMENT_ID));
  for (const [label, values] of [
    ["Model evidence strength", suggestions.map(item => item ? evidenceStrength(item.evidence_strength) : "Not suggested by model")],
    ["Model reason", suggestions.map(item => item ? item.reason : "No saved suggestion reason")]
  ]) {
    const line = element("tr");
    const heading = element("th", "", label);
    heading.scope = "row";
    line.append(heading);
    for (const value of values) line.append(element("td", "", value));
    body.append(line);
  }
  const important = ["THIRD_PARTY_NAME", "THIRD_PARTY_NORMALISED_NAME", "ENGAGEMENT_NAME", "ENGAGEMENT_DESCRIPTION_TEXT", "SERVICE_CATEGORY_L1_NAME", "PRIMARY_BENEFICIARY_COUNTRY_TERRITORY_ISO_NAME"];
  const fields = [...new Set([...important, ...matches.flatMap(item => Object.keys(item))])];
  let visibleFields = 0;
  for (const field of fields) {
    if (field === "ENGAGEMENT_ID" || !matches.some(item => Object.hasOwn(item, field))) continue;
    const values = matches.map(item => item[field] ?? "");
    const different = new Set(values).size > 1;
    if (matches.length > 1 && differencesOnly && !different) continue;
    const line = element("tr", different ? "different" : "");
    const heading = element("th", "", field);
    heading.scope = "row";
    if (different) heading.append(element("span", "difference-label", "Different"));
    line.append(heading);
    for (const value of values) line.append(element("td", "", value === "" ? "Not recorded" : String(value)));
    body.append(line);
    visibleFields++;
  }
  table.append(body);
  wrapper.append(table);
  if (!visibleFields) wrapper.append(element("p", "field-note", "No differing catalog fields. Clear the differences filter to inspect shared values."));
}

function splitCitations(value) {
  const citations = {classification: [], linking: [], unassigned: []};
  for (const line of String(value || "").split(/\r?\n/)) {
    if (!line.trim()) continue;
    if (line.startsWith("Classification:")) citations.classification.push(line);
    else if (line.startsWith("Engagement:")) citations.linking.push(line);
    else citations.unassigned.push(line);
  }
  return citations;
}

function classificationDetails(row, sources, citations) {
  const details = disclosure("Classification evidence and supplier details");
  details.classList.add("classification-evidence");
  const fields = element("div", "source-grid");
  addField(fields, "Processing status", row.processing_status);
  addField(fields, "Original model classification", modelLabel(row));
  addField(fields, "Key root cause", row.key_root_cause);
  const evidence = element("section", "field evidence-links");
  evidence.append(element("h4", "", "Evidence columns · open source"));
  for (const name of row.evidence_column) {
    const target = [...sources.querySelectorAll(".source-field")].find(field => field.dataset.sourceName === name);
    if (target) {
      evidence.append(button(name, () => {
        sources.open = true;
        for (const field of sources.querySelectorAll(".source-highlight")) field.classList.remove("source-highlight");
        target.classList.add("source-highlight");
        focusSection(target);
      }, "button evidence-link"));
    } else {
      evidence.append(element("span", "evidence-unavailable", name + " · source field unavailable"));
    }
  }
  if (!row.evidence_column.length) evidence.append(element("p", "field-note", "No evidence column names recorded."));
  fields.append(evidence);
  addField(fields, "Classification citations (not verified)", citations.classification.join("\n") || "No classification citations recorded.");
  if (row.classification === "SUPPLIER") {
    for (const [label, value] of [["Supplier base name", row.supplier_name], ["Product or service", row.supplier_product_or_service], ["Supplier action or failure", row.supplier_action_or_failure], ["Causal explanation", row.supplier_causal_explanation], ["Accountability reason", row.supplier_accountability_reason], ["Additional supplier information", row.supplier_more_info]]) addField(fields, label, value);
  }
  details.append(fields);
  if (citations.unassigned.length) {
    addField(details, "Unassigned legacy citations (stage unknown)", citations.unassigned.join("\n"));
    details.append(element("p", "field-note", "These saved excerpts have no stage label. They are not assigned to Classification or Linking and are not verified."));
  }
  return details;
}

function linkingDetails(row, citations) {
  const details = disclosure("Linking evidence and engagement details");
  details.classList.add("linking-evidence");
  const fields = element("div", "source-grid");
  for (const [label, value] of [
    ["Linking status", row.link_status],
    ["Base name used for search", row.link_supplier_name],
    ["Model default engagement", row.linked_engagement_id],
    ["Model recommendation", row.link_reason],
    ["Link evidence strength", evidenceStrength(row.link_confidence)],
    ["Name matches", row.link_match_count],
    ["LLM candidates", row.link_candidate_count],
    ["Model suggestions", row.link_suggestion_count]
  ]) addField(fields, label, value);
  if (row.link_error) addField(fields, "Finding error", row.link_error);
  addField(fields, "Linking citations (not verified)", citations.linking.join("\n") || "No linking citations recorded.");
  details.append(fields);
  if (row.link_status === "NOT_APPLICABLE" || row.link_status === "SKIPPED") {
    details.append(element("p", "field-note", "Linking is not applicable or was skipped for the current classification. No current engagement proposal is available."));
  }
  for (let number = 1; number <= 5; number++) {
    const prefix = "link_" + number + "_";
    const id = row[prefix + "engagement_id"];
    if (!id) continue;
    const suggestion = disclosure("Model suggestion " + number + " · " + id);
    addField(suggestion, "Reason", row[prefix + "reason"]);
    addField(suggestion, "Link evidence strength", evidenceStrength(row[prefix + "evidence_strength"]));
    details.append(suggestion);
  }
  const saved = {};
  for (const [key, value] of Object.entries(row)) {
    if (key.startsWith("ENG_") && value !== "") saved[key.slice(4)] = value;
  }
  if (Object.keys(saved).length) {
    const snapshot = engagementDetails(saved, "Saved current engagement details");
    snapshot.append(element("p", "field-note", "Catalog values for the saved selection. A human choice can differ from the model default above."));
    details.append(snapshot);
  }
  return details;
}

function inputDetails(row) {
  const details = disclosure("Original incident fields");
  const fields = element("div", "source-grid");
  for (const item of row.input_fields) {
    const field = addField(fields, item.name, item.value);
    field.classList.add("source-field");
    field.dataset.sourceName = item.name;
    field.tabIndex = -1;
  }
  details.append(fields);
  return details;
}


function showBottlenecks(counts) {
  const container = $("bottleneck-list");
  container.replaceChildren();
  for (const [stage, label] of [["processing", "Awaiting processing"], ["classification", "Classification"], ["supplier", "Supplier name"], ["engagement", "Engagement"], ["complete", "Review complete"]]) {
    const control = button("", () => {
      activeFilter = "total";
      $("search").value = "";
      $("review-filter").value = stage;
      renderRecords();
      focusSection($("incident-list"));
    }, "bottleneck-button");
    control.dataset.stage = stage;
    control.setAttribute("aria-controls", "incident-list");
    control.append(element("strong", "", String(counts[stage] ?? 0)), element("span", "", label));
    container.append(control);
  }
}

function setupScenarioGuide() {
  // Illustrations only: these steps never call the API or modify incident records.
  const scenarios = [
    {
      title: "1 · Supplier approval",
      context: "Synthetic incident: Atlas Cloud's gateway change interrupts a service.",
      steps: [
        ["Automatic proposal", "The model classifies SUPPLIER, extracts Atlas Cloud and proposes DEMO-ENG-01.", "The proposal is saved; human approval is pending."],
        ["Classification approved", "The reviewer confirms Supplier responsibility.", "Supplier-name review is now available."],
        ["Supplier name approved", "The reviewer confirms the recorded Atlas Cloud base name.", "The reviewer can decide on an engagement."],
        ["Engagement approved", "The reviewer explicitly accepts DEMO-ENG-01.", "Review complete with one human-confirmed link."]
      ]
    },
    {
      title: "2 · Supplier correction",
      context: "Synthetic incident: Supplier responsibility is clear, but the extracted name is wrong.",
      steps: [
        ["Automatic proposal", "The model returns SUPPLIER with Delta Networks and proposes DEMO-ENG-10.", "The reviewer first approves Supplier classification."],
        ["Name corrected", "The reviewer selects Nimbus Cloud from the supplier catalog and records: The incident notes name Nimbus Cloud as the provider.", "The corrected name is saved. Earlier engagement approval is reset."],
        ["Finding runs again", "Illustrated outcome: Python finds Nimbus Cloud matches; the model suggests DEMO-ENG-22.", "In the live workflow this reruns matching and linking. This walkthrough makes no model call."],
        ["New proposal reviewed", "The reviewer inspects the replacement suggestions and explicitly approves DEMO-ENG-22.", "The latest default and the human choice remain separately visible."]
      ]
    },
    {
      title: "3 · Uncertain resolved",
      context: "Synthetic incident: The model cannot determine the accountable party.",
      steps: [
        ["Unresolved model result", "Classification is UNCERTAIN. Automatic engagement matching is skipped.", "The incident waits at classification; later reviews remain locked."],
        ["Human resolves classification", "The reviewer checks the source notes, selects Disagree and chooses SUPPLIER with a recorded explanation.", "UNCERTAIN remains the original model result. The human decision is Supplier."],
        ["Supplier selected", "The reviewer chooses Atlas Cloud from the supplier catalog and records the supporting reason.", "The live workflow finds engagements for that name; the guide illustrates this step only."],
        ["Engagement reviewed", "After inspecting the options, the reviewer chooses None of these with a reason.", "Review complete without a human-confirmed link."]
      ]
    }
  ];
  let selectedScenario = 0;
  let selectedStep = 0;
  function renderScenario() {
    const scenario = scenarios[selectedScenario];
    $("scenario-tabs").replaceChildren();
    for (let index = 0; index < scenarios.length; index++) {
      const control = button(scenarios[index].title, () => {
        selectedScenario = index;
        selectedStep = 0;
        renderScenario();
        $("scenario-tabs").children[index].focus();
      });
      control.setAttribute("aria-pressed", String(index === selectedScenario));
      $("scenario-tabs").append(control);
    }
    const [title, explanation, outcome] = scenario.steps[selectedStep];
    const content = $("scenario-content");
    content.replaceChildren(
      element("p", "field-note", scenario.context),
      element("p", "eyebrow", "Illustrated step " + (selectedStep + 1) + " of " + scenario.steps.length),
      element("h3", "scenario-step", title),
      element("p", "", explanation),
      element("p", "scenario-outcome", outcome)
    );
    const previous = button("Previous step", () => {
      selectedStep--;
      renderScenario();
      focusSection(content);
    });
    previous.disabled = selectedStep === 0;
    const next = button("Next step", () => {
      selectedStep++;
      renderScenario();
      focusSection(content);
    }, "button primary");
    next.disabled = selectedStep === scenario.steps.length - 1;
    const restart = button("Restart scenario", () => {
      selectedStep = 0;
      renderScenario();
      focusSection(content);
    });
    $("scenario-controls").replaceChildren(previous, next, restart);
    content.tabIndex = -1;
  }
  renderScenario();
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
    if (["processing", "classification", "supplier", "engagement"].includes(reviewFilter) && row.next_action.stage !== reviewFilter) return false;
    const searchText = [row.incident_id, incidentTitle(row), row.supplier_name, row.effective_supplier_name, row.classification, row.linked_engagement_id, row.reviewed_engagement_id].join(" ").toLowerCase();
    return !query || searchText.includes(query);
  });
  let label = "All incidents";
  for (const control of document.querySelectorAll("[data-filter]")) {
    const selected = control.dataset.filter === activeFilter;
    control.setAttribute("aria-pressed", String(selected));
    if (selected) label = control.querySelector("span").textContent;
  }
  for (const control of document.querySelectorAll("[data-stage]")) {
    control.setAttribute("aria-pressed", String(control.dataset.stage === reviewFilter));
  }
  $("results-heading").textContent = label;
  $("filter-summary").textContent = visible.length + " of " + records.length + " incidents shown";
  $("dashboard-empty").hidden = visible.length > 0;
  $("dashboard-empty").textContent = "No incidents match " + label.toLowerCase() + " and the selected search or review filter.";
  $("incident-list").replaceChildren(...visible.map(recordCard));
}

function showDashboard(data) {
  records = data.incidents || [];
  supplierCatalogCount = data.supplier_catalog_count || 0;
  supplierCountries = data.supplier_countries || [];
  engagementCache.clear();
  $("mode").textContent = data.demo ? "Synthetic demonstration" : "Incident review";
  $("demo-note").hidden = !data.demo;
  for (const key of ["total", "HSBC", "SUPPLIER", "UNCERTAIN", "failed", "pending"]) $(key + "-count").textContent = data.counts[key] ?? 0;
  $("review-complete-count").textContent = data.counts.review_complete ?? 0;
  $("review-pending-count").textContent = data.counts.review_pending ?? 0;
  $("human-linked-count").textContent = data.counts.human_linked ?? 0;
  $("review-progress").max = Math.max(1, data.counts.total || 0);
  $("review-progress").value = data.counts.review_complete || 0;
  $("overview-text").textContent = data.overview;
  showBottlenecks(data.bottlenecks);
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
setupScenarioGuide();
loadDashboard();
