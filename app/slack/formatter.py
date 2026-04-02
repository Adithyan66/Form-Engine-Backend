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
                            "text": {"type": "plain_text", "text": opt["text"][:75]},
                            "value": opt["value"],
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
                                "text": opt["text"][:75],
                                "emoji": True,
                            },
                            "action_id": f"suggestion_{field_id}_{i + j}",
                            "value": opt["value"],
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
                "text": ":white_check_mark: *Service completed!* All fields have been filled.",
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
                "text": "Hello! :wave: I can help you with our services. Please select a service to get started:",
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


def build_home_tab_blocks(form, collected_data, missing_fields, status):
    """Build Block Kit blocks for the Slack Home Tab showing form progress."""
    blocks = []

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": form.get("title", "Form"), "emoji": True},
    })

    total = len(form.get("fields", []))
    filled = total - len(missing_fields)
    if status == "complete":
        status_text = ":white_check_mark: *Complete* — All fields filled!"
    else:
        status_text = f":pencil2: *In Progress* — {filled}/{total} fields filled"

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": status_text},
    })
    blocks.append({"type": "divider"})

    field_map = {f["field_id"]: f["label"] for f in form.get("fields", [])}

    if collected_data:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Collected Values*"},
        })
        for field_id, value in collected_data.items():
            label = field_map.get(field_id, field_id)
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{label}:*  {value}"},
            })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "_No values collected yet. Start chatting with the bot!_"},
        })

    if missing_fields and status != "complete":
        blocks.append({"type": "divider"})
        missing_labels = [field_map.get(fid, fid) for fid in missing_fields]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Remaining:*  " + ", ".join(missing_labels),
            },
        })

    return blocks


def build_home_tab_no_form_blocks(forms):
    """Build Home Tab blocks when no active form exists."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Welcome!", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No active service. Select one below or send me a message to get started.",
            },
        },
        {"type": "divider"},
    ]

    if forms:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": f["title"][:75],
                        "emoji": True,
                    },
                    "action_id": f"select_form_{f['form_id']}",
                    "value": f["form_id"],
                    "style": "primary",
                }
                for f in forms
            ],
        })

    return blocks
