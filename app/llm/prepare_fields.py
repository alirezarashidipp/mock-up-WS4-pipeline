from app.models import InputField


FIELD_ORDER = (
    # Incident and problem narrative.
    "INCIDENT_SHORT_DESCRIPTION",
    "INCIDENT_DESCRIPTION",
    "IT_PROBLEM_SUMMARY",
    "IT_PROBLEM_DESCRIPTION",
    "PROBLEM_TASK_SHORT_DESCRIPTION",
    "PROBLEM_TASK_DESCRIPTION",
    "MAJOR_INCIDENT_SUMMARY",
    # Recorded causes.
    "ROOT_CAUSE_NOTES",
    "IT_INCIDENT_CAUSE_DETAILS",
    "PROBLEM_TASK_CAUSE_NOTES",
    "ROOT_CAUSE_CODE",
    "CAUSING_CHANGE_ID",
    # Closure, resolution, and fix details.
    "PROBLEM_CLOSE_NOTES",
    "IT_PROBLEM_CLOSE_NOTES",
    "INCIDENT_RESOLUTION_DESCRIPTION",
    "INCIDENT_RESOLUTION_NOTES",
    "IT_PROBLEM_RESOLUTION_DESCRIPTION",
    "IT_PROBLEM_RESOLUTION_DETAILS",
    "PROBLEM_TASK_CLOSE_NOTES",
    "PROBLEM_TASK_FIX_NOTES",
    "PROBLEM_TASK_WORKAROUND",
    "PROBLEM_TASK_READ_ACROSS_DETAILS",
    # Investigation history and additional evidence.
    "INCIDENT_WORK_NOTES",
    "PROBLEM_WORK_NOTES",
    "MAJOR_INCIDENT_FINDINGS",
    "ADDITIONAL_COMMENTS",
    # Supplier, product, service, and ownership context.
    "PROBLEM_TASK_SUPPLIER_NAME",
    "PROBLEM_TASK_UNLISTED_SUPPLIER_NAME",
    "CONFIGURATION_ITEM_NAME",
    "IT_PROBLEM_CONFIGURATION_ITEM_NAME",
    "PROBLEM_TASK_CMDB_CI_NAME",
    "IMPACTED_BUSINESS_SERVICE_NAME",
    "PROBLEM_TASK_BUSINESS_SERVICE_NAME",
    "INCIDENT_ASSIGNMENT_GROUP_NAME",
    "PROBLEM_TASK_ASSIGNMENT_GROUP_NAME",
    "ROOT_CAUSE_TECHNOLOGY_OWNING_ORG_L2_NAME",
)


def prepare_fields(row: dict[str, str], definitions: dict[str, str]) -> list[dict[str, str]]:
    names = [name for name in FIELD_ORDER if name in row]
    # Keep all remaining metadata and additional columns in their source order.
    for name in row:
        if name != "INCIDENT_ID" and name not in names:
            names.append(name)

    fields = []
    for name in names:
        field = InputField(name=name, description=definitions[name], value=row[name])
        fields.append(field.model_dump())
    return fields
