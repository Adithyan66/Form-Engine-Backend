"""Slack adapter layer: reuses core logic parameterized by user_id."""

import asyncio

from langfuse.langchain import CallbackHandler

from app.storage import read_json, write_json
from app.validation import get_missing_fields, get_currently_asking, get_suggestions
from app.llm import call_openai_next_question
from app.graph import form_graph


def get_available_forms():
    """Return list of {form_id, title}."""
    forms = read_json("forms.json")
    return [{"form_id": f["form_id"], "title": f["title"]} for f in forms]


def _mask_sensitive(form, collected_data):
    """Mask sensitive field values in response data."""
    safe = dict(collected_data)
    for field in form["fields"]:
        if field.get("type") == "password" and field["field_id"] in safe:
            safe[field["field_id"]] = "********"
    return safe


def select_form(user_id, form_id):
    """Initialize a form session for a user. Returns standard response dict."""
    forms = read_json("forms.json")
    form = next((f for f in forms if f["form_id"] == form_id), None)
    if not form:
        return {"status": "error", "message": "Form not found."}

    write_json("active_form.json", form, user_id=user_id)
    write_json("collected_data.json", {}, user_id=user_id)
    write_json("messages.json", [], user_id=user_id)

    missing = get_missing_fields(form, {})
    question = call_openai_next_question(form, {}, missing)

    first_asking, _ = get_currently_asking(form, {})
    write_json("currently_asking.json", {"field_id": first_asking}, user_id=user_id)

    messages = [{"role": "assistant", "content": question}]
    write_json("messages.json", messages, user_id=user_id)

    return {
        "status": "pending",
        "message": question,
        "collected_data": {},
        "missing_fields": missing,
        "invalid_fields": [],
        "suggestions": get_suggestions(form, {}, missing, currently_asking=first_asking),
    }


def process_message(user_id, message):
    """Process a chat message for a user. Returns standard response dict, or None if no active form."""
    form = read_json("active_form.json", user_id=user_id)
    if not form:
        return None

    collected_data = read_json("collected_data.json", user_id=user_id)
    messages = read_json("messages.json", user_id=user_id)
    messages.append({"role": "user", "content": message})

    initial_state = {
        "user_message": message,
        "form": form,
        "collected_data": collected_data,
        "messages": messages,
        "currently_asking": None,
        "currently_asking_field": None,
        "extracted": {},
        "is_uncertain": False,
        "is_update": False,
        "is_confirm": False,
        "is_deny": False,
        "is_skip": False,
        "is_wait": False,
        "intent": "normal",
        "delete_fields": [],
        "query": None,
        "query_answer": None,
        "deleted_labels": [],
        "pending_data": {},
        "invalid_fields": [],
        "candidate_data": {},
        "auto_filled": {},
        "resolved_data": {},
        "inferred": {},
        "all_conflicts": [],
        "clean_fields": {},
        "dropped_fields": [],
        "response_msg": "",
        "status": "pending",
        "result": None,
    }

    langfuse_handler = CallbackHandler()
    final_state = form_graph.invoke(initial_state, config={"callbacks": [langfuse_handler]})

    collected_data = final_state["collected_data"]
    response_msg = final_state["response_msg"]
    status = final_state["status"]
    invalid_fields = final_state.get("invalid_fields", [])

    write_json("collected_data.json", collected_data, user_id=user_id)
    messages.append({"role": "assistant", "content": response_msg})
    write_json("messages.json", messages, user_id=user_id)

    fid, _ = get_currently_asking(form, collected_data)
    write_json("currently_asking.json", {"field_id": fid}, user_id=user_id)

    missing = get_missing_fields(form, collected_data)
    new_asking, _ = get_currently_asking(form, collected_data)

    result = {
        "status": status,
        "message": response_msg,
        "collected_data": _mask_sensitive(form, collected_data),
        "missing_fields": missing,
        "invalid_fields": invalid_fields,
        "suggestions": get_suggestions(form, collected_data, missing, currently_asking=new_asking),
    }

    all_conflicts = final_state.get("all_conflicts", [])
    if all_conflicts:
        result["conflicts"] = [{"field": c["field"], "reason": c["reason"]} for c in all_conflicts]

    return result


def reset_session(user_id):
    """Clear all session data for a user."""
    write_json("active_form.json", None, user_id=user_id)
    write_json("collected_data.json", {}, user_id=user_id)
    write_json("messages.json", [], user_id=user_id)
    write_json("currently_asking.json", {"field_id": None}, user_id=user_id)


# Async wrappers for use in Slack Bolt async handlers
async def select_form_async(user_id, form_id):
    return await asyncio.to_thread(select_form, user_id, form_id)


async def process_message_async(user_id, message):
    return await asyncio.to_thread(process_message, user_id, message)


async def reset_session_async(user_id):
    return await asyncio.to_thread(reset_session, user_id)
