const $ = id => document.getElementById(id);
let dashboard = null;
let activeView = "engagements";
let reviewSaving = false;
let reviewStale = false;
const groupLabels = {
  hsbc: "HSBC · No link required",
  supplier: "Supplier · No confirmed match",
  other: "Uncertain / failed / skipped / other",
};

function textElement(tag, text, className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  return element;
}

function route(engagementId, incidentId) {
  const parameters = new URLSearchParams();
  parameters.set("engagement", engagementId);
  if (incidentId !== undefined) parameters.set("incident", incidentId);
  return "#" + parameters.toString();
}

function unlinkedRoute(group = "all", incidentId) {
  const parameters = new URLSearchParams({view: "unlinked", group});
  if (incidentId !== undefined) parameters.set("incident", incidentId);
  return "#" + parameters.toString();
}

function incidentRoute(incidentId, classification = "all") {
  const parameters = new URLSearchParams({view: "incidents"});
  if (classification !== "all") parameters.set("classification", classification);
  if (incidentId !== undefined) parameters.set("incident", incidentId);
  return "#" + parameters.toString();
}

function hasReviewViews() {
  return Boolean(dashboard?.human_review && Array.isArray(dashboard.all_incidents) && Array.isArray(dashboard.all_engagements));
}

function listedEngagements() {
  if (hasReviewViews()) return dashboard.all_engagements;
  return dashboard.engagements;
}

function reviewReturnRoute(incidentId, parameters, serverRoute) {
  if (!hasReviewViews()) return serverRoute;
  if (parameters.get("view") === "incidents") {
    return incidentRoute(incidentId, parameters.get("classification") || "all");
  }
  if (parameters.has("engagement")) return route(parameters.get("engagement"), incidentId);
  return serverRoute;
}

function navigationLink(label, href) {
  const link = textElement("a", label);
  link.href = href;
  return link;
}

function addField(container, label, value) {
  const section = document.createElement("section");
  section.append(textElement("h3", label), textElement("p", value === "" || value == null ? "Not recorded" : value, "record-text"));
  container.append(section);
}

function addDisclosure(container, title, fields) {
  const details = document.createElement("details");
  details.append(textElement("summary", title));
  const content = textElement("div", "", "incident-secondary");
  for (const [name, value] of Object.entries(fields)) addField(content, name, value);
  details.append(content);
  container.append(details);
}

function linkEvidenceStrength(incident) {
  const value = incident.link_confidence;
  if (value == null || String(value).trim() === "") return "Not recorded";
  const scale = incident.link_confidence_scale;
  if (scale === "0-4") return evidenceStrength(value);
  if (scale != null && String(scale).trim() !== "") return "Unknown score scale";
  const score = String(value).trim();
  if (!/^(0|[1-9][0-9]?|100)$/.test(score)) return "Invalid score";
  return "Legacy confidence: " + score + "/100 (not converted)";
}

function evidenceStrength(value) {
  if (value == null || String(value).trim() === "") return "Not recorded";
  const score = String(value).trim();
  if (!/^[0-4]$/.test(score)) return "Invalid score";
  const labels = ["Unsupported", "Weak", "Moderate", "Strong", "Very strong"];
  return score + "/4 · " + labels[Number(score)];
}

function reviewBadge(label, status) {
  const labels = {pending: "Pending", confirmed: "Confirmed", rejected: "Rejected", invalidated: "Invalidated", not_applicable: "Not applicable"};
  const known = Object.hasOwn(labels, status);
  return textElement("span", label + ": " + (known ? labels[status] : "Not recorded"), "review-badge review-" + (known ? status : "pending"));
}

function addReviewBadges(container, incident) {
  if (!dashboard.human_review) return;
  const badges = textElement("div", "", "review-badges");
  badges.append(reviewBadge("Classification", incident.hitl_classification), reviewBadge("Link", incident.hitl_link));
  container.append(badges);
}

function setReviewBusy(busy) {
  reviewSaving = busy;
  $("reload").disabled = busy;
  for (const controls of document.querySelectorAll(".review-controls")) {
    controls.disabled = busy || reviewStale || controls.dataset.available !== "true";
  }
}

async function saveReview(incident, target, decision, reason = "") {
  if (reviewSaving || reviewStale) return;
  const parameters = new URLSearchParams(location.hash.slice(1));
  setReviewBusy(true);
  $("message").hidden = true;
  $("review-progress").hidden = true;
  try {
    const response = await fetch("/api/review", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({INCIDENT_ID: incident.INCIDENT_ID, target, decision, reason, version: incident.review_version}),
    });
    const data = await response.json();
    if (!response.ok) {
      reviewStale = response.status === 409;
      throw new Error(data.error || "Could not save the review. Refresh before trying again.");
    }
    setReviewBusy(false);
    applyDashboardData(data);
    const nextRoute = reviewReturnRoute(incident.INCIDENT_ID, parameters, data.review_route);
    if (nextRoute) history.replaceState(null, "", nextRoute);
    render(true);
    $("message").textContent = (target === "classification" ? "Classification" : "Link") + " review saved: " + decision + ".";
    $("message").className = "message";
    $("message").hidden = false;
  } catch (error) {
    $("review-progress").hidden = true;
    $("message").textContent = error.message + (reviewStale ? " Click Refresh to load the latest saved review." : "");
    $("message").className = "message error";
    $("message").hidden = false;
  } finally {
    setReviewBusy(false);
  }
}

function addReviewPanel(container, incident, target) {
  const isClassification = target === "classification";
  const label = isClassification ? "Classification" : "Engagement link";
  const status = isClassification ? incident.hitl_classification : incident.hitl_link;
  const reason = isClassification ? incident.hitl_classifivation_reasninb : incident.hitl_link_reasoning;
  const classificationAvailable = incident.processing_status === "success" && ["HSBC", "SUPPLIER", "UNCERTAIN"].includes(incident.classification);
  const hasProposal = classificationAvailable && incident.classification === "SUPPLIER" && incident.link_status === "MATCHED" && Boolean(incident.linked_engagement_id);
  const available = isClassification ? classificationAvailable : hasProposal && incident.hitl_classification === "confirmed";
  const panel = textElement("section", "", "review-panel");
  if (status === "confirmed" || status === "rejected" || status === "invalidated") panel.classList.add("review-state-" + status);
  panel.append(textElement("h3", label + " review"), reviewBadge(label, status));
  if (reason) panel.append(textElement("p", reason, "record-text"));
  let explanation;
  if (isClassification) {
    explanation = classificationAvailable ? "Is the model classification correct? No requires a reason and invalidates the engagement link." : "No successful classification is available to review.";
  } else if (!hasProposal) {
    explanation = "No proposed engagement link is available to review. HSBC and UNCERTAIN do not enter linking.";
  } else if (incident.hitl_classification !== "confirmed") {
    explanation = "Confirm the classification first. A rejected classification invalidates this link.";
  } else {
    explanation = "Is the proposed engagement correct? Rejecting this link leaves the classification confirmed.";
  }
  panel.append(textElement("p", explanation, "field-note"));
  const controls = document.createElement("fieldset");
  controls.className = "review-controls";
  controls.dataset.available = String(available);
  controls.disabled = !available || reviewSaving || reviewStale;
  controls.append(textElement("legend", label + " decision", "review-legend"));
  const buttons = textElement("div", "", "review-actions");
  const yes = textElement("button", "Yes", "button");
  const no = textElement("button", "No", "button");
  yes.type = no.type = "button";
  yes.id = "review-" + target + "-yes";
  no.id = "review-" + target + "-no";
  yes.addEventListener("click", () => saveReview(incident, target, "confirmed"));
  const form = document.createElement("form");
  form.className = "review-rejection";
  form.hidden = true;
  const input = document.createElement("textarea");
  input.id = "review-" + target + "-reason";
  input.name = "reason";
  input.rows = 3;
  input.maxLength = 2000;
  input.required = true;
  input.value = status === "rejected" ? reason || "" : "";
  const reasonLabel = textElement("label", "Reason for rejecting " + label.toLowerCase() + " (required)");
  reasonLabel.htmlFor = input.id;
  const save = textElement("button", "Save rejection", "button");
  save.type = "submit";
  const cancel = textElement("button", "Cancel", "button");
  cancel.type = "button";
  cancel.addEventListener("click", () => { form.hidden = true; no.focus(); });
  no.addEventListener("click", () => { form.hidden = false; input.focus(); });
  input.addEventListener("input", () => input.setCustomValidity(""));
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!input.value.trim()) {
      input.setCustomValidity("Enter a reason before rejecting.");
      input.reportValidity();
      return;
    }
    saveReview(incident, target, "rejected", input.value.trim());
  });
  const formActions = textElement("div", "", "review-actions");
  formActions.append(save, cancel);
  form.append(reasonLabel, input, formActions);
  buttons.append(yes, no);
  controls.append(buttons, form);
  panel.append(controls);
  container.append(panel);
}

function addHumanReview(card, incident) {
  if (!dashboard.human_review) return;
  const review = textElement("div", "", "review-grid");
  addReviewPanel(review, incident, "classification");
  addReviewPanel(review, incident, "link");
  card.append(review);
  addField(card, "Human-confirmed engagement", incident.hitl_linked_engagement_id || "None. Both classification and link must be confirmed.");
}

function showEngagements() {
  $("page-title").textContent = "Engagements";
  $("subtitle").textContent = dashboard.human_review ? "Choose an engagement to review its proposed incident links." : "Choose an engagement to explore its linked incidents.";
  const query = $("search").value.trim().toLowerCase();
  const allEngagements = listedEngagements();
  const engagements = allEngagements.filter(item => [item.name, item.company, item.engagement_id].join(" ").toLowerCase().includes(query));
  if (hasReviewViews()) {
    const overview = textElement("section", "", "eng-catalog-overview");
    overview.append(textElement("h2", "Total engagements: " + dashboard.counts.total_engagements));
    overview.append(textElement("p", dashboard.engagement_scope_note, "field-note"));
    $("view").append(overview);
  }
  if (!engagements.length) {
    const empty = dashboard.human_review ? "No engagements in this view. Open Incident first to review saved incidents." : "No linked engagements yet. INC_LINKED.csv must contain matched incidents.";
    const message = allEngagements.length ? "No engagements match your search." : empty;
    $("view").append(textElement("p", message, "eng-empty"));
    return;
  }
  const cards = textElement("div", "", "eng-grid");
  for (const engagement of engagements) {
    const card = navigationLink("", route(engagement.engagement_id));
    card.className = "eng-card";
    card.append(textElement("p", engagement.company || "Unknown company", "eng-company"));
    card.append(textElement("h2", engagement.name || engagement.engagement_id));
    card.append(textElement("p", engagement.engagement_id, "eng-identifier"));
    const incidentLabel = dashboard.human_review ? " proposed incident link" : " linked incident";
    card.append(textElement("span", engagement.incidents.length + incidentLabel + (engagement.incidents.length === 1 ? "" : "s"), "eng-count"));
    if (dashboard.human_review) {
      const confirmed = engagement.incidents.filter(incident => incident.hitl_link === "confirmed").length;
      card.append(textElement("span", confirmed + " human-confirmed", "review-badge review-confirmed"));
    }
    cards.append(card);
  }
  $("view").append(cards);
}

function showEngagement(engagement) {
  $("eyebrow").textContent = engagement.company || "Unknown company";
  $("page-title").textContent = engagement.name || engagement.engagement_id;
  $("subtitle").textContent = engagement.engagement_id + " · " + engagement.incidents.length + (dashboard.human_review ? " proposed incident links" : " linked incidents");
  const list = textElement("div", "", "eng-incident-list");
  for (const incident of engagement.incidents) {
    const link = navigationLink("", route(engagement.engagement_id, incident.INCIDENT_ID));
    link.className = "eng-incident-link";
    link.append(textElement("p", incident.INCIDENT_ID, "eng-identifier"));
    link.append(textElement("h2", incident.INCIDENT_SHORT_DESCRIPTION || "Incident details"));
    link.append(textElement("p", incident.link_reason || "No link explanation recorded.", "eng-preview"));
    link.append(textElement("span", "Link evidence strength: " + linkEvidenceStrength(incident), "eng-count"));
    addReviewBadges(link, incident);
    list.append(link);
  }
  $("view").append(textElement("h2", dashboard.human_review ? "Model-proposed incident links · all review statuses" : "Linked incidents"), list);
  if (!engagement.incidents.length) $("view").append(textElement("p", "No incidents to review for this engagement.", "eng-empty"));
  const fields = textElement("div", "", "eng-fields");
  addDisclosure(fields, "Engagement information", engagement.fields);
  $("view").append(fields);
}

function showAllIncidents(classification) {
  $("page-title").textContent = "Incidents";
  $("subtitle").textContent = "Start with any saved incident, inspect its classification and model match, then review the decisions.";
  const query = $("search").value.trim().toLowerCase();
  const list = textElement("div", "", "eng-incident-list");
  for (const incident of dashboard.all_incidents) {
    const classified = incident.processing_status === "success" && ["HSBC", "SUPPLIER", "UNCERTAIN"].includes(incident.classification);
    if (classification === "failed" && classified) continue;
    if (classification !== "all" && classification !== "failed" && (!classified || incident.classification !== classification)) continue;
    const searchable = [incident.INCIDENT_ID, incident.INCIDENT_SHORT_DESCRIPTION, incident.INCIDENT_DESCRIPTION, incident.supplier_name, incident.classification, incident.linked_engagement_id, incident.ENG_ENGAGEMENT_NAME, incident.link_reason].join(" ").toLowerCase();
    if (!searchable.includes(query)) continue;
    const link = navigationLink("", incidentRoute(incident.INCIDENT_ID, classification));
    link.className = "eng-incident-link";
    link.append(textElement("p", incident.INCIDENT_ID, "eng-identifier"));
    link.append(textElement("h2", incident.INCIDENT_SHORT_DESCRIPTION || "Incident details"));
    let classificationText = "Failed / unclassified";
    if (classified) classificationText = incident.classification;
    link.append(textElement("p", "Model classification: " + classificationText, "eng-preview"));
    let match = "No model match · " + incident.link_status;
    if (incident.link_status === "MATCHED") match = "Model proposal: " + incident.linked_engagement_id + " · " + (incident.ENG_ENGAGEMENT_NAME || "Engagement name not recorded");
    link.append(textElement("p", match, "eng-preview"));
    addReviewBadges(link, incident);
    list.append(link);
  }
  $("view").append(textElement("p", "Showing " + list.children.length + " of " + dashboard.all_incidents.length + " saved incidents", "field-note"));
  if (!list.children.length) {
    $("view").append(textElement("p", "No incidents match this classification and search.", "eng-empty"));
    return;
  }
  $("view").append(list);
}

function showUnlinked(group) {
  $("page-title").textContent = "Unlinked incidents";
  $("subtitle").textContent = dashboard.human_review ? "Review these classifications or inspect rejected and invalidated links. Original model proposals remain available in the details." : "HSBC incidents need no engagement link. Supplier incidents here have no confirmed match. Uncertain classifications, failures, and skipped linking are listed separately.";
  const query = $("search").value.trim().toLowerCase();
  const list = textElement("div", "", "eng-incident-list");
  let total = 0;
  for (const [category, incidents] of Object.entries(dashboard.unlinked_groups)) {
    if (group !== "all" && category !== group) continue;
    total += incidents.length;
    for (const incident of incidents) {
      const searchable = [incident.INCIDENT_ID, incident.INCIDENT_SHORT_DESCRIPTION, incident.supplier_name, incident.link_reason, incident.classification, incident.link_status].join(" ").toLowerCase();
      if (!searchable.includes(query)) continue;
      const link = navigationLink("", unlinkedRoute(category, incident.INCIDENT_ID));
      link.className = "eng-incident-link";
      link.append(textElement("p", groupLabels[category], "eng-company"));
      link.append(textElement("p", incident.INCIDENT_ID || "Incident ID not recorded", "eng-identifier"));
      link.append(textElement("h2", incident.INCIDENT_SHORT_DESCRIPTION || "Incident details"));
      if (incident.classification === "SUPPLIER") link.append(textElement("p", "Supplier: " + (incident.supplier_name || "Unknown"), "eng-preview"));
      link.append(textElement("p", incident.link_reason || "No link explanation recorded.", "eng-preview"));
      link.append(textElement("span", (dashboard.human_review ? "Model link status: " : "Link status: ") + incident.link_status, "eng-count"));
      addReviewBadges(link, incident);
      list.append(link);
    }
  }
  if (!list.children.length) {
    $("view").append(textElement("p", total ? "No incidents match your search." : "No unlinked incidents in this group.", "eng-empty"));
    return;
  }
  $("view").append(textElement("p", "Showing " + list.children.length + " of " + total + " incidents", "field-note"), list);
}

function showIncident(engagement, incident, group) {
  $("eyebrow").textContent = engagement ? engagement.company || "Unknown company" : groupLabels[group] || "INCIDENT REVIEW / WS4";
  $("page-title").textContent = incident.INCIDENT_ID;
  $("subtitle").textContent = incident.INCIDENT_SHORT_DESCRIPTION || "Incident details";
  const card = textElement("article", "", "incident-card");
  addHumanReview(card, incident);
  if (dashboard.human_review && incident.linked_engagement_id) {
    addField(card, "Original model engagement proposal", (incident.ENG_ENGAGEMENT_NAME || incident.linked_engagement_id) + " · " + incident.linked_engagement_id);
    addField(card, "Model link status", incident.link_status);
    addField(card, "Model link explanation", incident.link_reason);
  } else if (engagement) {
    addField(card, "Linked engagement", (engagement.name || engagement.engagement_id) + " · " + engagement.engagement_id);
    addField(card, "Why this engagement was selected", incident.link_reason);
  } else {
    let engagementLink = groupLabels[group] || "No model engagement selected";
    if (dashboard.human_review && incident.processing_status === "success" && ["HSBC", "UNCERTAIN"].includes(incident.classification)) {
      engagementLink = "Not applicable for " + incident.classification;
    }
    addField(card, "Engagement link", engagementLink);
    addField(card, "Link status", incident.link_status);
    addField(card, "Why this incident is not linked", incident.link_reason);
    if (incident.link_error) addField(card, "Link processing error", incident.link_error);
    if (incident.error) addField(card, "Classification processing error", incident.error);
  }
  const decisions = textElement("div", "", "eng-decision-grid");
  addField(decisions, dashboard.human_review ? "Model classification" : "Classification", incident.classification);
  addField(decisions, "Attribution evidence strength", evidenceStrength(incident.attribution_evidence_strength));
  addField(decisions, "Link evidence strength", linkEvidenceStrength(incident));
  card.append(decisions, textElement("p", "Attribution evidence strength rates support for assigning responsibility to HSBC or Supplier. Link evidence strength separately rates support for one engagement match among the supplied candidates. Neither score is a probability or measured accuracy. For UNCERTAIN classification, 0-2 describes limited attribution evidence, not confidence in uncertainty.", "field-note"));
  addDisclosure(card, "Attribution evidence strength scale · 0 to 4", {
    "0 · Unsupported": "No recorded causal evidence distinguishes HSBC from Supplier.",
    "1 · Weak": "Only indirect references or unconfirmed suspicion support attributing a party; key causal facts are missing.",
    "2 · Moderate": "Some causal evidence exists, but a material contradiction or missing causal link remains.",
    "3 · Strong": "Concrete facts support the responsible party and causal mechanism; remaining gaps do not substantially challenge the tag.",
    "4 · Very strong": "A clear documented causal finding has supporting details and no unresolved material counterevidence in the supplied record.",
    "Reading the score": "A score of 4 does not mean 100% accuracy. Repeated copies of one statement are not independent evidence. This score does not rate supplier-name extraction or engagement matching. Older results without this score show Not recorded.",
  });
  addDisclosure(card, "Link evidence strength scale · 0 to 4", {
    "0 · Unsupported": "No recorded evidence supports a unique engagement link; no engagement is selected.",
    "1 · Weak": "Only indirect references or general overlap support a possible engagement link.",
    "2 · Moderate": "Relevant service or context details exist, but material gaps or ambiguity remain.",
    "3 · Strong": "Concrete incident and engagement facts support the match and distinguish the candidate.",
    "4 · Very strong": "An explicit documented connection has consistent supporting details and no unresolved material contradiction among the supplied candidates.",
    "Reading the score": "Selected links use 1-4; undecided model responses use 0-2. A score of 4 does not mean 100% accuracy. Without a model score, this field shows Not recorded. Older scores are labelled Legacy confidence and are not converted.",
  });
  addField(card, "Incident description", incident.INCIDENT_DESCRIPTION);
  addField(card, "Key root cause", incident.key_root_cause);
  addField(card, "Classification rationale", incident.decision_rationale);
  if (incident.classification === "SUPPLIER") {
    const supplier = textElement("div", "", "supplier-grid");
    for (const [label, name] of [
      ["Supplier", "supplier_name"], ["Product or service", "supplier_product_or_service"],
      ["Supplier action or failure", "supplier_action_or_failure"], ["Causal explanation", "supplier_causal_explanation"],
      ["Accountability reason", "supplier_accountability_reason"], ["Additional supplier information", "supplier_more_info"]
    ]) addField(supplier, label, incident[name]);
    card.append(supplier);
  }
  const incidentFields = {}, engagementFields = {}, linkFields = {};
  for (const [name, value] of Object.entries(incident)) {
    if (name === "review_version") continue;
    if (name.startsWith("ENG_")) engagementFields[name.slice(4)] = value;
    else if (name.startsWith("link_") || name === "linked_engagement_id") linkFields[name] = value;
    else incidentFields[name] = value;
  }
  addDisclosure(card, "Link evidence and processing details", linkFields);
  addDisclosure(card, "All incident fields", incidentFields);
  if (engagement || Object.values(engagementFields).some(value => value)) addDisclosure(card, "All engagement fields", engagementFields);
  $("view").append(card);
}

function configureNavigation(view, isDetail) {
  if (activeView !== view) $("search").value = "";
  activeView = view;
  for (const name of ["engagements", "incidents", "unlinked"]) {
    if (name === view) $(name + "-tab").setAttribute("aria-current", "page");
    else $(name + "-tab").removeAttribute("aria-current");
  }
  $("search-panel").hidden = isDetail;
  $("unlinked-filter-panel").hidden = view !== "unlinked" || isDetail;
  $("classification-filter-panel").hidden = view !== "incidents" || isDetail;
  $("counts").hidden = isDetail;
  $("supplier-funnel").hidden = view !== "incidents";
  $("linking-overview").hidden = view === "incidents";
  $("search-label").textContent = "Find an engagement or company";
  $("search").placeholder = "Name, company, or engagement ID";
  $("eyebrow").textContent = "SUPPLIER ENGAGEMENTS / WS4";
  if (view === "incidents") {
    $("search-label").textContent = "Find an incident";
    $("search").placeholder = "Incident ID, description, supplier, or engagement";
    $("eyebrow").textContent = "INCIDENT FIRST / WS4";
  }
  if (view === "unlinked") {
    $("search-label").textContent = "Find an unlinked incident";
    $("search").placeholder = "Incident ID, description, supplier, or link reason";
    $("eyebrow").textContent = "UNLINKED INCIDENTS / WS4";
  }
}

function showMissingRecord(destination) {
  $("page-title").textContent = "Record not found";
  $("subtitle").textContent = "This record is not in the current data. Return to " + destination + ".";
}

function renderIncidentView(parameters) {
  let classification = parameters.get("classification") || "all";
  if (!["all", "HSBC", "SUPPLIER", "UNCERTAIN", "failed"].includes(classification)) classification = "all";
  $("classification-filter").value = classification;
  const incidentId = parameters.get("incident");
  if (incidentId === null) {
    showAllIncidents(classification);
    return;
  }
  $("breadcrumbs").append(navigationLink("All incidents", incidentRoute(undefined, classification)));
  const incident = dashboard.all_incidents.find(item => item.INCIDENT_ID === incidentId);
  if (!incident) {
    showMissingRecord("all incidents");
    return;
  }
  const engagement = listedEngagements().find(item => item.engagement_id === incident.linked_engagement_id);
  showIncident(engagement, incident);
}

function renderUnlinkedView(parameters) {
  const group = parameters.get("group") || "all";
  const incidentId = parameters.get("incident");
  $("unlinked-filter").value = group;
  const incidents = Object.hasOwn(groupLabels, group) ? dashboard.unlinked_groups[group] : null;
  const incident = incidents?.find(item => item.INCIDENT_ID === incidentId);
  if (incidentId !== null) $("breadcrumbs").append(navigationLink("Unlinked incidents", unlinkedRoute(group)));
  if ((group !== "all" && !incidents) || (incidentId !== null && !incident)) {
    showMissingRecord("unlinked incidents");
  } else if (incidentId !== null) {
    showIncident(null, incident, group);
  } else {
    showUnlinked(group);
  }
}

function renderEngagementView(parameters) {
  const engagementId = parameters.get("engagement");
  const incidentId = parameters.get("incident");
  if (engagementId === null && incidentId === null) {
    showEngagements();
    return;
  }
  $("breadcrumbs").append(navigationLink("All engagements", "#"));
  const engagement = listedEngagements().find(item => item.engagement_id === engagementId);
  const incident = engagement?.incidents.find(item => item.INCIDENT_ID === incidentId);
  if (!engagement || (incidentId !== null && !incident)) {
    showMissingRecord("all engagements");
  } else if (incidentId !== null) {
    $("breadcrumbs").append(textElement("span", "/", "eng-separator"), navigationLink(engagement.name || engagement.engagement_id, route(engagementId)));
    showIncident(engagement, incident);
  } else {
    showEngagement(engagement);
  }
}

function render(focus = false) {
  $("view").replaceChildren();
  $("breadcrumbs").replaceChildren();
  if (!dashboard) return;
  const parameters = new URLSearchParams(location.hash.slice(1));
  let view = "engagements";
  if (parameters.get("view") === "unlinked") view = "unlinked";
  if (parameters.get("view") === "incidents" && hasReviewViews()) view = "incidents";
  const isDetail = parameters.has("engagement") || parameters.has("incident");
  configureNavigation(view, isDetail);
  if (view === "incidents") {
    renderIncidentView(parameters);
  } else if (view === "unlinked") {
    renderUnlinkedView(parameters);
  } else {
    renderEngagementView(parameters);
  }
  document.title = $("page-title").textContent + (dashboard.human_review ? " | Human review | HSBC" : " | HSBC");
  if (focus) $("page-title").focus();
}

function applyDashboardMode(humanReview) {
  const source = humanReview ? "HUMAN_REVIEW.csv" : "INC_LINKED.csv";
  document.body.classList.toggle("human-review-app", humanReview);
  if (!humanReview) $("review-progress").hidden = true;
  $("engagements-tab").textContent = humanReview ? "Engagement first" : "Engagements";
  $("incidents-tab").hidden = !hasReviewViews();
  $("brand-caption").textContent = humanReview ? "WS4 / HUMAN REVIEW" : "WS4 / ENGAGEMENTS";
  $("footer-title").textContent = humanReview ? "HSBC · Human review / WS4" : "HSBC · Engagement explorer / WS4";
  $("source-file").textContent = humanReview ? "Reviews: HUMAN_REVIEW.csv · Engagement catalog: ENG_ALL.csv" : "Source: " + source;
  $("source-note").textContent = "Counts cover saved rows in " + source + ". A partial run may contain only part of the input.";
  $("linked-count-label").textContent = humanReview ? "Active proposed links" : "Linked incidents";
  $("engagements-count-label").textContent = humanReview ? "Active engagements" : "Engagements";
  $("companies-count-label").textContent = humanReview ? "Active companies" : "Companies";
  $("linking-note").textContent = humanReview ? "Active proposals include pending and confirmed reviews. Engagement lists retain every original model proposal, including rejected or invalidated links. A human-confirmed link requires both decisions to be confirmed." : "Successful SUPPLIER incidents are eligible for matching. A confirmed link is not guaranteed. HSBC and UNCERTAIN do not enter matching.";
  groupLabels.other = humanReview ? "Rejected / invalidated / uncertain / other" : "Uncertain / failed / skipped / other";
}

function applyDashboardData(data) {
  dashboard = data;
  applyDashboardMode(Boolean(data.human_review));
  for (const [name, count] of Object.entries(data.counts)) {
    const counter = $(name + "-count");
    if (counter) counter.textContent = count;
  }
  $("funnel-supplier-count").textContent = data.counts.eligible_incidents;
  $("funnel-confirmed-count").textContent = data.counts.review_link_confirmed ?? "—";
  let completeReviewCounts = true;
  for (const counter of document.querySelectorAll("#review-progress [id$='-count']")) {
    const count = data.counts[counter.id.slice(0, -6)];
    if (!Number.isInteger(count) || count < 0) completeReviewCounts = false;
  }
  $("review-progress").hidden = !data.human_review || !completeReviewCounts;
  for (const option of $("unlinked-filter").options) {
    const total = option.value === "all" ? data.counts.unlinked_incidents : data.unlinked_groups[option.value].length;
    const label = option.value === "all" ? "All unlinked incidents" : groupLabels[option.value];
    option.textContent = label + " (" + total + ")";
  }
  $("demo-note").hidden = !data.demo;
  $("mode").textContent = data.human_review ? "Human review" : "Linked incidents";
  if (data.demo) $("mode").textContent = (data.human_review ? "Human review · " : "") + "Demo · synthetic data";
}

async function loadDashboard() {
  if (reviewSaving) return;
  $("reload").disabled = true;
  $("message").hidden = true;
  $("demo-note").hidden = true;
  $("review-progress").hidden = true;
  $("incidents-tab").hidden = true;
  $("classification-filter-panel").hidden = true;
  $("supplier-funnel").hidden = true;
  $("mode").textContent = "Loading…";
  $("eyebrow").textContent = "SUPPLIER ENGAGEMENTS / WS4";
  $("page-title").textContent = "Loading engagements…";
  $("subtitle").textContent = "Reading saved incidents.";
  dashboard = null;
  $("view").replaceChildren();
  $("breadcrumbs").replaceChildren();
  for (const counter of document.querySelectorAll("[id$='-count']")) counter.textContent = "—";
  try {
    const response = await fetch("/api/engagements", {cache: "no-store"});
    const data = await response.json();
    applyDashboardMode(Boolean(data.human_review));
    if (!response.ok) throw new Error(data.error || "Could not read linked incidents.");
    reviewStale = false;
    applyDashboardData(data);
    render();
  } catch (error) {
    dashboard = null;
    $("review-progress").hidden = true;
    $("incidents-tab").hidden = true;
    $("classification-filter-panel").hidden = true;
    $("supplier-funnel").hidden = true;
    $("view").replaceChildren();
    $("breadcrumbs").replaceChildren();
    for (const counter of document.querySelectorAll("[id$='-count']")) counter.textContent = "—";
    $("page-title").textContent = "Engagements unavailable";
    $("subtitle").textContent = "Check the saved CSV and refresh.";
    $("mode").textContent = "Unavailable";
    $("message").textContent = error.message;
    $("message").className = "message error";
    $("message").hidden = false;
    document.title = "Engagements unavailable | HSBC";
  } finally {
    $("reload").disabled = false;
  }
}

$("reload").addEventListener("click", loadDashboard);
$("search").addEventListener("input", () => render());
$("unlinked-filter").addEventListener("change", () => { location.hash = unlinkedRoute($("unlinked-filter").value); });
$("classification-filter").addEventListener("change", () => { location.hash = incidentRoute(undefined, $("classification-filter").value); });
window.addEventListener("hashchange", () => render(true));
loadDashboard();
