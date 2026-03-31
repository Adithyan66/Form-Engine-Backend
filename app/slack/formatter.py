"""Convert standard response dicts to Slack Block Kit format."""

import re


def markdown_to_slack_mrkdwn(text):
    """Convert markdown bold/italic to Slack mrkdwn format.

    Markdown: **bold**, *italic*, ***bold italic***
    Slack mrkdwn: *bold*, _italic_, *_bold italic_*
    """
    # Replace ***bold italic*** first (longest match) -> placeholder
    text = re.sub(r'\*\*\*(.+?)\*\*\*', lambda m: f'\x00BI{m.group(1)}BI\x00', text)
    # Replace **bold** -> placeholder
    text = re.sub(r'\*\*(.+?)\*\*', lambda m: f'\x00B{m.group(1)}B\x00', text)
    # Replace remaining *italic* -> _italic_
    text = re.sub(r'\*(.+?)\*', r'_\1_', text)
    # Restore placeholders
    text = re.sub(r'\x00BI(.+?)BI\x00', r'*_\1_*', text)
    text = re.sub(r'\x00B(.+?)B\x00', r'*\1*', text)
    return text


def format_response(response):
    """Convert standard response dict to Slack Block Kit blocks."""
    blocks = []

    # Main message text
    message = response.get("message", "")
    if message:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": markdown_to_slack_mrkdwn(message),
            },
        })

    # Suggestions as buttons or dropdown
    suggestions = response.get("suggestions", [])
    for suggestion in suggestions:
        field_id = suggestion["field_id"]
        label = suggestion["label"]
        options = suggestion.get("options", [])

        if not options:
            continue

        # Use static_select dropdown for large option lists
        if len(options) > 20:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Choose *{label}*:"},
                "accessory": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": f"Select {label}",
                    },
                    "action_id": f"suggestion_select_{field_id}",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": opt[:75]},
                            "value": opt,
                        }
                        for opt in options[:100]  # Slack max 100 options
                    ],
                },
            })
        else:
            # Use buttons, chunked in groups of 5
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Choose *{label}*:"},
            })
            for i in range(0, len(options), 5):
                chunk = options[i : i + 5]
                blocks.append({
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": opt[:75],
                                "emoji": True,
                            },
                            "action_id": f"suggestion_{field_id}_{i + j}",
                            "value": opt,
                        }
                        for j, opt in enumerate(chunk)
                    ],
                })

    # Completion indicator
    if response.get("status") == "complete":
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":white_check_mark: *Form completed!* All fields have been filled.",
            },
        })

    return blocks


def build_form_selection_blocks(forms):
    """Build Block Kit blocks for form selection menu."""
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Hello! :wave: I can help you fill out forms. Please select a form to get started:",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": form["title"][:75],
                        "emoji": True,
                    },
                    "action_id": f"select_form_{form['form_id']}",
                    "value": form["form_id"],
                    "style": "primary",
                }
                for form in forms
            ],
        },
    ]
    return blocks


def build_reset_confirmation_blocks():
    """Confirmation blocks after reset."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":arrows_counterclockwise: Session reset. Send any message to start again!",
            },
        },
    ]
