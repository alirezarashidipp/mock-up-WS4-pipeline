const $ = id => document.getElementById(id);
let dashboard = null;
let activeView = "engagements";
const groupLabels = {
  hsbc: "HSBC · No link required",
  supplier: "Supplier · No confirmed match",
  other: "Failed / skipped / other",
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

function confidence(value) {
  return value === "" || value == null ? "Not recorded" : value + "/100";
}

function showEngagements() {
  $("page-title").textContent = "Engagements";
  $("subtitle").textContent = "Choose an engagement to explore its linked incidents.";
  const query = $("search").value.trim().toLowerCase();
  const engagements = dashboard.engagements.filter(item => [item.name, item.company, item.engagement_id].join(" ").toLowerCase().includes(query));
  if (!engagements.length) {
    const message = dashboard.engagements.length ? "No engagements match your search." : "No linked engagements yet. INC_LINKED.csv must contain matched incidents.";
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
    card.append(textElement("span", engagement.incidents.length + " linked incident" + (engagement.incidents.length === 1 ? "" : "s"), "eng-count"));
    cards.append(card);
  }
  $("view").append(cards);
}

function showEngagement(engagement) {
  $("eyebrow").textContent = engagement.company || "Unknown company";
  $("page-title").textContent = engagement.name || engagement.engagement_id;
  $("subtitle").textContent = engagement.engagement_id + " · " + engagement.incidents.length + " linked incidents";
  const list = textElement("div", "", "eng-incident-list");
  for (const incident of engagement.incidents) {
    const link = navigationLink("", route(engagement.engagement_id, incident.INCIDENT_ID));
    link.className = "eng-incident-link";
    link.append(textElement("p", incident.INCIDENT_ID, "eng-identifier"));
    link.append(textElement("h2", incident.INCIDENT_SHORT_DESCRIPTION || "Incident details"));
    link.append(textElement("p", incident.link_reason || "No link explanation recorded.", "eng-preview"));
    link.append(textElement("span", "Link confidence: " + confidence(incident.link_confidence), "eng-count"));
    list.append(link);
  }
  $("view").append(textElement("h2", "Linked incidents"), list);
  const fields = textElement("div", "", "eng-fields");
  addDisclosure(fields, "Engagement information", engagement.fields);
  $("view").append(fields);
}

function showUnlinked(group) {
  $("page-title").textContent = "Unlinked incidents";
  $("subtitle").textContent = "HSBC incidents need no engagement link. Supplier incidents here have no confirmed match; failed or skipped processing is listed separately.";
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
      link.append(textElement("span", "Link status: " + incident.link_status, "eng-count"));
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
  $("eyebrow").textContent = engagement ? engagement.company || "Unknown company" : groupLabels[group];
  $("page-title").textContent = incident.INCIDENT_ID;
  $("subtitle").textContent = incident.INCIDENT_SHORT_DESCRIPTION || "Incident details";
  const card = textElement("article", "", "incident-card");
  if (engagement) {
    addField(card, "Linked engagement", (engagement.name || engagement.engagement_id) + " · " + engagement.engagement_id);
    addField(card, "Why this engagement was selected", incident.link_reason);
  } else {
    addField(card, "Engagement link", groupLabels[group]);
    addField(card, "Link status", incident.link_status);
    addField(card, "Why this incident is not linked", incident.link_reason);
    if (incident.link_error) addField(card, "Link processing error", incident.link_error);
    if (incident.error) addField(card, "Classification processing error", incident.error);
  }
  const decisions = textElement("div", "", "eng-decision-grid");
  addField(decisions, "Classification", incident.classification);
  addField(decisions, "Classification confidence", confidence(incident.llm_confidence));
  addField(decisions, "Link confidence", confidence(incident.link_confidence));
  card.append(decisions, textElement("p", "Confidence values are model-reported, not measured accuracy.", "field-note"));
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
    if (name.startsWith("ENG_")) engagementFields[name.slice(4)] = value;
    else if (name.startsWith("link_") || name === "linked_engagement_id") linkFields[name] = value;
    else incidentFields[name] = value;
  }
  addDisclosure(card, "Link evidence and processing details", linkFields);
  addDisclosure(card, "All incident fields", incidentFields);
  if (engagement || Object.values(engagementFields).some(value => value)) addDisclosure(card, "All engagement fields", engagementFields);
  $("view").append(card);
}

function render(focus = false) {
  $("view").replaceChildren();
  $("breadcrumbs").replaceChildren();
  if (!dashboard) return;
  const parameters = new URLSearchParams(location.hash.slice(1));
  const engagementId = parameters.get("engagement");
  const incidentId = parameters.get("incident");
  const view = parameters.get("view") === "unlinked" ? "unlinked" : "engagements";
  const group = parameters.get("group") || "all";
  const isDetail = engagementId !== null || incidentId !== null;
  if (activeView !== view) $("search").value = "";
  activeView = view;
  for (const name of ["engagements", "unlinked"]) {
    if (name === view) $(name + "-tab").setAttribute("aria-current", "page");
    else $(name + "-tab").removeAttribute("aria-current");
  }
  $("search-panel").hidden = isDetail;
  $("unlinked-filter-panel").hidden = view !== "unlinked" || isDetail;
  $("counts").hidden = isDetail;
  $("search-label").textContent = view === "unlinked" ? "Find an unlinked incident" : "Find an engagement or company";
  $("search").placeholder = view === "unlinked" ? "Incident ID, description, supplier, or link reason" : "Name, company, or engagement ID";
  $("eyebrow").textContent = view === "unlinked" ? "UNLINKED INCIDENTS / WS4" : "SUPPLIER ENGAGEMENTS / WS4";
  if (view === "unlinked") {
    $("unlinked-filter").value = group;
    const incidents = Object.hasOwn(groupLabels, group) ? dashboard.unlinked_groups[group] : null;
    const incident = incidents?.find(item => item.INCIDENT_ID === incidentId);
    if (incidentId !== null) $("breadcrumbs").append(navigationLink("Unlinked incidents", unlinkedRoute(group)));
    if ((group !== "all" && !incidents) || (incidentId !== null && !incident)) {
      $("page-title").textContent = "Record not found";
      $("subtitle").textContent = "This record is not in the current CSV. Return to unlinked incidents.";
    } else if (incidentId !== null) {
      showIncident(null, incident, group);
    } else {
      showUnlinked(group);
    }
  } else if (engagementId === null && incidentId === null) {
    showEngagements();
  } else {
    $("breadcrumbs").append(navigationLink("All engagements", "#"));
    const engagement = dashboard.engagements.find(item => item.engagement_id === engagementId);
    const incident = engagement?.incidents.find(item => item.INCIDENT_ID === incidentId);
    if (!engagement || (incidentId !== null && !incident)) {
      $("page-title").textContent = "Record not found";
      $("subtitle").textContent = "This record is not in the current CSV. Return to all engagements.";
    } else if (incidentId !== null) {
      $("breadcrumbs").append(textElement("span", "/", "eng-separator"), navigationLink(engagement.name || engagement.engagement_id, route(engagementId)));
      showIncident(engagement, incident);
    } else {
      showEngagement(engagement);
    }
  }
  document.title = $("page-title").textContent + " | HSBC";
  if (focus) $("page-title").focus();
}

async function loadDashboard() {
  $("reload").disabled = true;
  $("message").hidden = true;
  $("demo-note").hidden = true;
  $("mode").textContent = "Loading…";
  $("eyebrow").textContent = "SUPPLIER ENGAGEMENTS / WS4";
  $("page-title").textContent = "Loading engagements…";
  $("subtitle").textContent = "Reading INC_LINKED.csv.";
  dashboard = null;
  $("view").replaceChildren();
  $("breadcrumbs").replaceChildren();
  for (const counter of document.querySelectorAll("[id$='-count']")) counter.textContent = "—";
  try {
    const response = await fetch("/api/engagements", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not read linked incidents.");
    dashboard = data;
    for (const [name, count] of Object.entries(data.counts)) $(name + "-count").textContent = count;
    $("other-count-panel").hidden = data.counts.other_unlinked_incidents === 0;
    for (const option of $("unlinked-filter").options) {
      const total = option.value === "all" ? data.counts.unlinked_incidents : data.unlinked_groups[option.value].length;
      const label = option.value === "all" ? "All unlinked incidents" : groupLabels[option.value];
      option.textContent = label + " (" + total + ")";
    }
    $("demo-note").hidden = !data.demo;
    $("mode").textContent = data.demo ? "Demo · synthetic data" : "Linked incidents";
    render();
  } catch (error) {
    dashboard = null;
    $("view").replaceChildren();
    $("breadcrumbs").replaceChildren();
    for (const counter of document.querySelectorAll("[id$='-count']")) counter.textContent = "—";
    $("page-title").textContent = "Engagements unavailable";
    $("subtitle").textContent = "Check INC_LINKED.csv and refresh.";
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
window.addEventListener("hashchange", () => render(true));
loadDashboard();
