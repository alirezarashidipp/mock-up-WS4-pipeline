from app.csv_files import append_record


def save_linked(path, incident, engagement, engagement_columns, link):
    extra = {}
    for name in engagement_columns:
        extra[f"ENG_{name}"] = engagement.get(name, "")
    extra.update(link)
    extra["link_incident_columns"] = ", ".join(link["link_incident_columns"])
    extra["link_engagement_columns"] = ", ".join(link["link_engagement_columns"])
    if incident.keys() & extra.keys():
        print("Link output columns overlap input columns. Use the original LLM_OUTPUT.csv.")
        return False
    record = dict(incident)
    record.update(extra)
    saved, error = append_record(path, record)
    if not saved:
        print(error)
    return saved
