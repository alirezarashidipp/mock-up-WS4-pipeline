"""Human decisions and engagement refresh, independent of the HTTP app."""

import csv
import re
import unicodedata

from app.incidents import (
    CLASSES, REVIEW_DEFAULTS, SUPPLIERS_FILE, apply_link_result,
    engagement_values, get_incident, row_version, save_incident,
)
from app.linking.candidates import find_candidates
from app.linking.linking import catalog_hash, find_engagements, load_max_candidates, read_engagements
from app.models import empty_link


def normalize_supplier_search(value):
    text = unicodedata.normalize("NFKD", value).casefold()
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(re.findall(r"[^\W_]+", text))


def read_supplier_catalog(path=SUPPLIERS_FILE):
    """Read base names and optional countries without changing the source file."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = [row for row in csv.reader(file, strict=True) if any(value.strip() for value in row)]
        if not rows:
            return [], "SUPPLIER_NAME.csv has no base names. Add names before correcting a supplier."

        header = [value.strip().casefold() for value in rows[0]]
        name_index = 0
        country_index = None
        column_count = 1
        if header == ["supplier_name"]:
            rows = rows[1:]
        elif len(header) != 1:
            if len(header) != 2 or set(header) != {"supplier_name", "country"}:
                raise ValueError
            name_index = header.index("supplier_name")
            country_index = header.index("country")
            column_count = 2
            rows = rows[1:]

        suppliers = {}
        for row in rows:
            if len(row) != column_count:
                raise ValueError
            name = row[name_index].strip()
            country = row[country_index].strip() if country_index is not None else ""
            if not name:
                if country:
                    raise ValueError
                continue
            if name not in suppliers:
                suppliers[name] = {"name": name, "countries": []}
            countries = suppliers[name]["countries"]
            country_key = normalize_supplier_search(country)
            if country_key and all(normalize_supplier_search(value) != country_key for value in countries):
                countries.append(country)
        if not suppliers:
            return [], "SUPPLIER_NAME.csv has no base names. Add names before correcting a supplier."
        return list(suppliers.values()), ""
    except FileNotFoundError:
        return [], "SUPPLIER_NAME.csv is missing. Supplier corrections require the base-name catalog."
    except (OSError, UnicodeError, csv.Error, ValueError):
        return [], "SUPPLIER_NAME.csv needs one base-name column, or SUPPLIER_NAME and COUNTRY headers with one country per row."


def search_supplier_catalog(suppliers, query, country, offset):
    terms = normalize_supplier_search(query).split()
    country_key = normalize_supplier_search(country)
    matches = []
    for supplier in suppliers:
        name = normalize_supplier_search(supplier["name"])
        if not all(term in name for term in terms):
            continue
        countries = supplier["countries"]
        if country_key and not any(normalize_supplier_search(value) == country_key for value in countries):
            continue
        matches.append(supplier)
    return {
        "suppliers": matches[offset:offset + 50],
        "total": len(matches),
        "offset": offset,
        "has_more": offset + 50 < len(matches),
        "error": "",
    }


def usable_supplier_name(name):
    return (name or "").strip().casefold() not in ("", "unknown", "n/a", "n a", "none", "null", "not known", "not available")


def classification_complete(row):
    return row["classification_review_status"] in ("approved", "disagree") and row["reviewed_classification"] in ("HSBC", "SUPPLIER")


def supplier_complete(row):
    return (
        classification_complete(row)
        and row["reviewed_classification"] == "SUPPLIER"
        and row["supplier_review_status"] in ("approved", "disagree")
        and usable_supplier_name(row["reviewed_supplier_name"])
    )


def effective_classification(row):
    if row["classification_review_status"] in ("approved", "disagree"):
        return row["reviewed_classification"]
    return row["classification"] if row["processing_status"] == "success" else ""


def effective_supplier_name(row):
    if supplier_complete(row):
        return row["reviewed_supplier_name"]
    if effective_classification(row) == "SUPPLIER":
        return row.get("supplier_name", "")
    return ""


def review_complete(row):
    if not classification_complete(row):
        return False
    if row["reviewed_classification"] == "HSBC":
        return True
    return supplier_complete(row) and row["engagement_review_status"] in ("approved", "disagree")


def apply_classification_review(row, decision):
    if row["processing_status"] == "pending":
        raise ValueError("Wait for classification processing before reviewing this incident.")
    updated = dict(row)
    if decision.decision == "approved":
        if row["processing_status"] != "success" or row["classification"] not in ("HSBC", "SUPPLIER"):
            raise ValueError("Choose HSBC or SUPPLIER and explain the decision for an unresolved model result.")
        selected = row["classification"]
    else:
        selected = decision.classification
        if selected not in CLASSES:
            raise ValueError("Choose HSBC, SUPPLIER, or UNCERTAIN.")
    updated.update(REVIEW_DEFAULTS)
    updated["classification_review_status"] = decision.decision
    updated["reviewed_classification"] = selected
    updated["classification_review_reason"] = decision.reason.strip() if decision.decision == "disagree" else ""
    if selected == "SUPPLIER" and row["link_status"] == "RUNNING":
        apply_link_result(updated, empty_link(status="PENDING", reason="Review changed while suggestions were running."))
    if selected != "SUPPLIER":
        status = "NOT_APPLICABLE" if selected == "HSBC" else "SKIPPED"
        apply_link_result(updated, empty_link(status=status, reason="Human classification does not permit engagement linking."))
        updated.update({name: "" for name in row if name.startswith("ENG_")})
        updated["supplier_review_status"] = "not_applicable"
        updated["engagement_review_status"] = "not_applicable"
    return updated


def apply_supplier_review(row, decision, supplier_names):
    if not classification_complete(row) or row["reviewed_classification"] != "SUPPLIER":
        raise ValueError("Approve or correct Supplier classification before reviewing its name.")
    if decision.decision == "approved":
        if row["processing_status"] != "success" or row["classification"] != "SUPPLIER" or not usable_supplier_name(row.get("supplier_name", "")):
            raise ValueError("Choose a supplier base name from the catalog and give a reason.")
        name = row["supplier_name"]
    else:
        name = decision.supplier_name
        if name not in supplier_names or not usable_supplier_name(name):
            raise ValueError("Choose a supplier from the current SUPPLIER_NAME.csv catalog.")
    updated = dict(row)
    updated["supplier_review_status"] = decision.decision
    updated["reviewed_supplier_name"] = name
    updated["supplier_review_reason"] = decision.reason.strip() if decision.decision == "disagree" else ""
    updated["engagement_review_status"] = "pending"
    updated["reviewed_engagement_id"] = ""
    updated["engagement_review_reason"] = ""
    return updated


def apply_engagement_review(row, decision, engagements_file):
    if not supplier_complete(row):
        raise ValueError("Complete classification and supplier-name reviews before reviewing engagement.")
    if row["link_status"] == "RUNNING":
        raise ValueError("Wait for engagement suggestions to finish before saving a decision.")
    if row["link_supplier_name"] != row["reviewed_supplier_name"]:
        raise ValueError("Refresh engagement suggestions for the current supplier before approving a link.")
    engagements = read_engagements(engagements_file)
    if row["link_catalog_hash"] != catalog_hash(engagements):
        raise ValueError("The engagement catalog changed. Refresh suggestions before saving a decision.")
    selected = decision.engagement_id
    if decision.decision == "approved":
        if not selected or selected != row["linked_engagement_id"]:
            raise ValueError("Approved must confirm the model default. Choose Disagree and give a reason to change it.")
    matches = find_candidates(row["link_supplier_name"], engagements, None)
    if selected and selected not in {item["ENGAGEMENT_ID"] for item in matches}:
        raise ValueError("Choose an engagement from the current supplier's matching catalog rows.")
    updated = dict(row)
    updated.update(engagement_values(row, engagements, selected))
    updated["engagement_review_status"] = decision.decision
    updated["reviewed_engagement_id"] = selected
    updated["engagement_review_reason"] = decision.reason.strip() if decision.decision == "disagree" else ""
    return updated


def refresh_engagements(row, results_file, engagements_file):
    """Save the changed name first, then recompute; discard a stale model response."""
    if not supplier_complete(row):
        raise ValueError("Complete classification and supplier-name reviews before refreshing engagements.")
    updated = dict(row)
    name = row["reviewed_supplier_name"]
    apply_link_result(updated, empty_link(name, status="RUNNING", reason="Finding engagement suggestions."))
    updated.update({key: "" for key in row if key.startswith("ENG_")})
    updated["engagement_review_status"] = "pending"
    updated["reviewed_engagement_id"] = ""
    updated["engagement_review_reason"] = ""
    running = save_incident(results_file, updated, row_version(row))
    try:
        max_candidates = load_max_candidates()
        engagements = read_engagements(engagements_file)
        engagement_values(running, engagements, "")
        proposal = find_engagements(running, engagements, name, max_candidates)
        proposal.update(engagement_values(running, engagements, proposal["linked_engagement_id"]))
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        proposal = empty_link(name, status="FAILED", reason="Could not prepare engagement suggestions. Check the catalog and settings, then retry.")
        proposal["link_error"] = type(error).__name__
    updated = dict(running)
    apply_link_result(updated, proposal)
    return save_incident(results_file, updated, row_version(running))


def save_review(decision, results_file, suppliers_file, engagements_file):
    row = get_incident(results_file, decision.incident_id, decision.version)
    if decision.decision == "disagree" and not decision.reason.strip():
        raise ValueError("Disagree requires a nonblank reason.")
    if decision.target == "classification":
        updated = apply_classification_review(row, decision)
    elif decision.target == "supplier":
        catalog, _ = read_supplier_catalog(suppliers_file)
        names = {supplier["name"] for supplier in catalog}
        updated = apply_supplier_review(row, decision, names)
    else:
        updated = apply_engagement_review(row, decision, engagements_file)
    if decision.target in ("classification", "supplier") and effective_classification(updated) == "SUPPLIER":
        updated.update({key: "" for key in row if key.startswith("ENG_")})
        if updated["linked_engagement_id"]:
            try:
                engagements = read_engagements(engagements_file)
                if updated["link_catalog_hash"] == catalog_hash(engagements):
                    updated.update(engagement_values(updated, engagements, updated["linked_engagement_id"]))
            except (OSError, UnicodeError, csv.Error, ValueError):
                # Classification review still works while the catalog is unavailable.
                pass
    saved = save_incident(results_file, updated, decision.version)
    if decision.target == "supplier":
        name_changed = saved["reviewed_supplier_name"] != saved["link_supplier_name"]
        missing_proposal = saved["link_status"] in ("PENDING", "SKIPPED", "NOT_APPLICABLE")
        if name_changed or missing_proposal:
            saved = refresh_engagements(saved, results_file, engagements_file)
    return saved
