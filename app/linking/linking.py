from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.llm_connection import llm_connection
from app.linking.candidates import find_candidates
from app.linking.save_csv import save_linked


class LinkInput(BaseModel):
    incident: dict[str, str]
    engagements: list[dict[str, str]]


class EngagementLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linked_engagement_id: str | None
    link_reason: str = Field(min_length=1)
    link_confidence: int = Field(
        ge=0,
        le=4,
        strict=True,
        json_schema_extra={"enum": [0, 1, 2, 3, 4]},
        description="Recorded support for a unique engagement link: 0 unsupported, 1 weak, 2 moderate, 3 strong, 4 very strong. Use 0-2 when no engagement is selected; selected links require 1-4. Not a probability.",
    )
    link_incident_columns: list[str]
    link_engagement_columns: list[str]


def select_engagement(client, model, incident, candidates, prompt):
    fields = {name: value for name, value in incident.items() if name != "INCIDENT_ID"}
    payload = LinkInput(incident=fields, engagements=candidates)
    schema = EngagementLink.model_json_schema()
    # Match the existing Azure-compatible response schema; Pydantic checks limits locally.
    for field in schema["properties"].values():
        for keyword in ("minLength", "minimum", "maximum"):
            field.pop(keyword, None)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": payload.model_dump_json()},
    ]
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "EngagementLink", "strict": True, "schema": schema},
    }
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format=response_format,
        store=False,
    )
    if not response.choices:
        return None
    choice = response.choices[0]
    if choice.finish_reason != "stop" or choice.message.refusal or not choice.message.content:
        return None
    result = EngagementLink.model_validate_json(choice.message.content)
    if not result.link_reason.strip():
        return None
    if result.linked_engagement_id is None and result.link_confidence > 2:
        return None
    if result.linked_engagement_id is not None and result.link_confidence == 0:
        return None
    if result.linked_engagement_id is not None:
        selected = [row for row in candidates if row["ENGAGEMENT_ID"] == result.linked_engagement_id]
        if len(selected) != 1 or not result.linked_engagement_id.strip():
            return None
        if not result.link_incident_columns or not result.link_engagement_columns:
            return None
    return result


def link_incident(incident, engagements, prompt, max_candidates=70):
    link = {
        "linked_engagement_id": "", "link_status": "UNDECIDED", "link_reason": "",
        "link_confidence": "", "link_incident_columns": [], "link_engagement_columns": [],
        "link_error": "",
    }
    if incident.get("processing_status") != "success":
        link.update(link_status="SKIPPED", link_reason="Incident classification did not succeed.")
        return link, {}
    classification = incident.get("classification")
    if classification == "HSBC":
        link.update(link_status="NOT_APPLICABLE", link_reason="HSBC incident; supplier engagement linking is not applicable.")
        return link, {}
    if classification == "UNCERTAIN":
        link.update(link_status="SKIPPED", link_reason="Classification is uncertain; supplier accountability is not established, so engagement matching was skipped.")
        return link, {}
    if classification != "SUPPLIER":
        link.update(link_status="FAILED", link_reason="Expected HSBC, SUPPLIER, or UNCERTAIN classification.", link_error="InvalidClassification")
        return link, {}
    candidates = find_candidates(incident.get("supplier_name", ""), engagements, max_candidates)
    if not candidates:
        link["link_reason"] = "Supplier name is missing or no similar supplier name was found in ENG_ALL.csv."
        return link, {}
    try:
        with llm_connection() as (client, model):
            result = select_engagement(client, model, incident, candidates, prompt)
    except (OpenAIError, ValidationError, ValueError) as error:
        link.update(link_status="FAILED", link_reason="Engagement request failed; check link_error.", link_error=type(error).__name__)
        return link, {}
    if result is None:
        link.update(link_status="FAILED", link_reason="Response was empty, refused, incomplete, or did not satisfy the linking response checks.", link_error="InvalidModelOutput")
        return link, {}
    link.update(result.model_dump())
    if result.linked_engagement_id is None:
        return link, {}
    link["link_status"] = "MATCHED"
    selected = next(row for row in candidates if row["ENGAGEMENT_ID"] == result.linked_engagement_id)
    return link, selected


def link_incidents(incidents, engagements, prompt, output_file, max_candidates=70):
    if not incidents or not engagements:
        print("LLM_OUTPUT.csv and ENG_ALL.csv must contain rows.")
        return 1
    columns = engagements[0].keys()
    if "ENGAGEMENT_ID" not in columns or not {"THIRD_PARTY_NAME", "THIRD_PARTY_NORMALISED_NAME"}.intersection(columns):
        print("ENG_ALL.csv needs ENGAGEMENT_ID and THIRD_PARTY_NAME or THIRD_PARTY_NORMALISED_NAME.")
        return 1
    for incident in incidents:
        link, engagement = link_incident(incident, engagements, prompt, max_candidates)
        if not save_linked(output_file, incident, engagement, columns, link):
            return 1
        print(f"Saved incident {incident['INCIDENT_ID']}: {link['link_status']}")
        if link["link_status"] == "FAILED":
            print("Stopped. Earlier results are saved; check link_error in INC_LINKED.csv.")
            return 1
    print(f"Output: {output_file}")
    return 0
