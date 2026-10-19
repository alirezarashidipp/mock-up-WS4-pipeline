from app.models import InputField


def prepare_fields(row: dict[str, str], definitions: dict[str, str]) -> list[dict[str, str]]:
    fields = []
    for name, value in row.items():
        if name != "ROW_ID":
            field = InputField(name=name, description=definitions[name], value=value)
            fields.append(field.model_dump())
    return fields
