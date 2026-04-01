"""Slack Bolt app with event and action handlers."""

import asyncio
import os
import re

from slack_bolt.async_app import AsyncApp

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
    build_home_tab_blocks,
    build_home_tab_no_form_blocks,
)
from app.validation import get_missing_fields
from app.storage import read_json

slack_app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN", ""),
)


# --- Helpers ---

async def _send_processing(client, channel):
    """Send a processing indicator and return its ts for later update."""
    result = await client.chat_postMessage(
        channel=channel,
        text=":hourglass_flowing_sand: Processing your request...",
    )
    return result["ts"]


async def _update_message(client, channel, ts, response):
    """Update the processing message with the actual response."""
    blocks = format_response(response)
    await client.chat_update(
        channel=channel,
        ts=ts,
        blocks=blocks,
        text=response.get("message") or "Here's the update.",
    )


async def _update_error(client, channel, ts):
    """Update the processing message with an error."""
    await client.chat_update(
        channel=channel,
        ts=ts,
        text=":x: Something went wrong. Please try again.",
        blocks=[],
    )


# --- Background task runners ---

async def _process_message_bg(client, channel, ts, user_id, text):
    """Background: run process_message and update the placeholder."""
    try:
        response = await process_message_async(user_id, text)
        if response is None:
            forms = get_available_forms()
            await client.chat_update(
                channel=channel,
                ts=ts,
                blocks=build_form_selection_blocks(forms),
                text="Please select a form.",
            )
            return
        await _update_message(client, channel, ts, response)
    except Exception as e:
        print(f"[Slack] ERROR processing message: {e}")
        await _update_error(client, channel, ts)


async def _select_form_bg(client, channel, ts, user_id, form_id):
    """Background: run select_form and update the placeholder."""
    try:
        response = await select_form_async(user_id, form_id)
        await _update_message(client, channel, ts, response)
    except Exception as e:
        print(f"[Slack] ERROR selecting form: {e}")
        await _update_error(client, channel, ts)


# --- Event: Home Tab opened ---

@slack_app.event("app_home_opened")
async def handle_home_tab(client, event):
    """Publish the Home Tab view when the user opens it."""
    user_id = event["user"]

    form = read_json("active_form.json", user_id=user_id)

    if not form:
        forms = get_available_forms()
        blocks = build_home_tab_no_form_blocks(forms)
    else:
        collected_data = read_json("collected_data.json", user_id=user_id)
        missing = get_missing_fields(form, collected_data)
        status = "complete" if not missing else "pending"
        blocks = build_home_tab_blocks(form, collected_data, missing, status)

    await client.views_publish(
        user_id=user_id,
        view={"type": "home", "blocks": blocks},
    )


# --- Event: Direct message ---

@slack_app.event("message")
async def handle_message(event, say, client):
    """Handle incoming DMs or channel messages."""
    user_id = event.get("user")
    text = (event.get("text") or "").strip()
    channel = event.get("channel")

    print(f"[Slack] Message from user {user_id}: {text}")

    # Ignore bot messages, message_changed, etc.
    if not user_id or event.get("bot_id") or event.get("subtype"):
        return

    # Reset command — lightweight, no background needed
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

    # Send processing indicator, then do heavy work in background
    ts = await _send_processing(client, channel)
    asyncio.create_task(_process_message_bg(client, channel, ts, user_id, text))


# --- Event: App mention in channels ---

@slack_app.event("app_mention")
async def handle_app_mention(event, say, client):
    """Handle @bot mentions in channels."""
    text = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
    event["text"] = text
    await handle_message(event, say, client)


# --- Action: Form selection button ---

@slack_app.action(re.compile(r"^select_form_"))
async def handle_form_selection(ack, body, client):
    """Handle form selection button clicks."""
    await ack()
    action = body["actions"][0]
    form_id = action["value"]
    user_id = body["user"]["id"]
    channel = body["channel"]["id"]

    ts = await _send_processing(client, channel)
    asyncio.create_task(_select_form_bg(client, channel, ts, user_id, form_id))


# --- Action: Suggestion button click ---

@slack_app.action(re.compile(r"^suggestion_"))
async def handle_suggestion_click(ack, body, client):
    """Handle suggestion button clicks -- normalize as a regular chat message."""
    await ack()
    action = body["actions"][0]
    option_value = action["value"]
    user_id = body["user"]["id"]
    channel = body["channel"]["id"]

    ts = await _send_processing(client, channel)
    asyncio.create_task(_process_message_bg(client, channel, ts, user_id, option_value))
