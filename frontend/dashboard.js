const $ = id => document.getElementById(id);
async function loadDashboard() {
  $("reload").disabled = true;
  $("message").hidden = true;
  try {
    const response = await fetch("/api/dashboard", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load final decisions.");
    $("mode").textContent = data.demo ? "Demo · synthetic data" : "Final decisions";
    $("demo-note").hidden = !data.demo;
    for (const key of ["total", "HSBC", "SUPPLIER", "CONFIRMED", "CORRECTED", "RESOLVED_UNDECIDED"]) {
      $(key + "-count").textContent = data.counts[key];
    }
    for (const name of ["HSBC", "SUPPLIER"]) {
      $(name + "-percent").textContent = data.percentages[name] + "%";
      $(name + "-meter").value = data.percentages[name];
    }
    $("final-rows").replaceChildren();
    $("dashboard-empty").hidden = data.records.length > 0;
    $("final-table").hidden = data.records.length === 0;
    for (const row of data.records) {
      const tr = document.createElement("tr");
      for (const value of [row.incident_id, row.summary, row.llm_class, row.final_class, row.user_reason, row.review_action.replaceAll("_", " "), new Date(row.review_date).toLocaleString()]) {
        const td = document.createElement("td"); td.textContent = value; tr.append(td);
      }
      $("final-rows").append(tr);
    }
  } catch (error) {
    $("message").textContent = error.message;
    $("message").className = "message error";
    $("message").hidden = false;
    $("final-rows").replaceChildren(); $("final-table").hidden = true; $("dashboard-empty").hidden = true;
    for (const element of document.querySelectorAll("[id$='-count'], [id$='-percent']")) element.textContent = "—";
    for (const meter of document.querySelectorAll("meter")) meter.value = 0;
  } finally { $("reload").disabled = false; }
}
$("reload").addEventListener("click", loadDashboard);
loadDashboard();
