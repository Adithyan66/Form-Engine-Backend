"""Slack Bolt app with event and action handlers."""

import os
import re

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.slack.handler import (
    get_available_forms,
    select_form_async,
    process_message_async,
    reset_session_async,
)
from app.slack.formatter import (
    format_response,
    build_form_selection_blocks,
    build_reset_confirmation_blocks,
)
from app.storage import read_json

slack_app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN", ""),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
)

slack_handler = AsyncSlackRequestHandler(slack_app)


# --- Event: Direct message ---

@slack_app.event("message")
async def handle_message(event, say):
    """Handle incoming DMs or channel messages."""
    user_id = event.get("user")
    text = (event.get("text") or "").strip()

    # Ignore bot messages, message_changed, etc.
    if not user_id or event.get("bot_id") or event.get("subtype"):
        return

    # Reset command
    if text.lower() in ("reset", "/reset", "start over", "clear"):
        await reset_session_async(user_id)
        await say(blocks=build_reset_confirmation_blocks(), text="Session reset.")
        return

    # Check if user has an active form
    active_form = read_json("active_form.json", user_id=user_id)

    if not active_form:
        forms = get_available_forms()
        await say(
            blocks=build_form_selection_blocks(forms),
            text="Please select a form.",
        )
        return

    # Process as chat message
    response = await process_message_async(user_id, text)
    if response is None:
        forms = get_available_forms()
        await say(
            blocks=build_form_selection_blocks(forms),
            text="Please select a form.",
        )
        return

    blocks = format_response(response)
    await say(blocks=blocks, text=response.get("message", ""))


# --- Event: App mention in channels ---

@slack_app.event("app_mention")
async def handle_app_mention(event, say):
    """Handle @bot mentions in channels."""
    text = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
    event["text"] = text
    await handle_message(event, say)


# --- Action: Form selection button ---

@slack_app.action(re.compile(r"^select_form_"))
async def handle_form_selection(ack, body, say):
    """Handle form selection button clicks."""
    await ack()
    action = body["actions"][0]
    form_id = action["value"]
    user_id = body["user"]["id"]

    response = await select_form_async(user_id, form_id)
    blocks = format_response(response)
    await say(blocks=blocks, text=response.get("message", ""))


# --- Action: Suggestion button click ---

@slack_app.action(re.compile(r"^suggestion_"))
async def handle_suggestion_click(ack, body, say):
    """Handle suggestion button clicks -- normalize as a regular chat message."""
    await ack()
    action = body["actions"][0]
    option_value = action["value"]
    user_id = body["user"]["id"]

    response = await process_message_async(user_id, option_value)
    if response is None:
        await say(text="No active form. Send a message to start.")
        return

    blocks = format_response(response)
    await say(blocks=blocks, text=response.get("message", ""))
