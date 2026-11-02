"""Human decisions and engagement refresh, independent of the HTTP app."""

import csv

from app.incidents import (
    CLASSES, REVIEW_DEFAULTS, SUPPLIERS_FILE, apply_link_result,
    engagement_values, get_incident, row_version, save_incident,
)
from app.linking.candidates import find_candidates
from app.linking.linking import catalog_hash, find_engagements, load_max_candidates, read_engagements
from app.models import empty_link


def supplier_options(path=SUPPLIERS_FILE):
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file, strict=True))
        names = []
        for row in rows:
            if not row:
                continue
            if len(row) != 1:
                raise ValueError
            name = row[0].strip()
            if not name or (not names and name.casefold() == "supplier_name"):
                continue
            if name not in names:
                names.append(name)
        if not names:
            return [], "SUPPLIER_NAME.csv has no base names. Add names before correcting a supplier."
        return names, ""
    except FileNotFoundError:
        return [], "SUPPLIER_NAME.csv is missing. Supplier corrections require the base-name catalog."
    except (OSError, UnicodeError, csv.Error, ValueError):
        return [], "SUPPLIER_NAME.csv must be a UTF-8 CSV with one supplier-name column."


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
        names, _ = supplier_options(suppliers_file)
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
