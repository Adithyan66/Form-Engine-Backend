import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")

# Files that are shared across all users (not per-session)
SHARED_FILES = {"forms.json"}

# Sensible defaults for missing session files
_DEFAULTS = {
    "collected_data.json": {},
    "messages.json": [],
    "currently_asking.json": {"field_id": None},
    "active_form.json": None,
}


def _resolve_path(filename, user_id=None):
    """Resolve file path: shared files stay in DATA_DIR, session files go to user dir."""
    if filename in SHARED_FILES or user_id is None:
        return os.path.join(DATA_DIR, filename)
    user_dir = os.path.join(SESSIONS_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, filename)


def read_json(filename, user_id=None):
    path = _resolve_path(filename, user_id)
    if not os.path.exists(path):
        return _DEFAULTS.get(filename)
    with open(path, "r") as f:
        return json.load(f)


def write_json(filename, data, user_id=None):
    path = _resolve_path(filename, user_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
