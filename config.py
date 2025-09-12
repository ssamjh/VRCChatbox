import string
import json
import os


def load_app_config():
    """Load application configuration from config.json"""
    config_file = "app_config.json"
    default_config = {
        "show_music": True,
        "shockosc": {
            "enabled": False,
            "mode": "static",  # "static" or "random"
            "static_intensity": 50,  # 0-100
            "random_min": 20,  # 0-100
            "random_max": 80,  # 0-100
            "duration": 1.0,  # 0.3-30.0 seconds
            "groups": ["leftleg", "rightleg"],  # ShockOSC groups to control
            "show_shock_info": True,  # Show shock percentage in chatbox
            "cooldown_delay": 5.0,  # Cooldown delay in seconds (0.0-60.0)
            "hold_time": 0.5,  # Required contact hold time in seconds (0.0-5.0)
            "openshock_token": "",  # OpenShock API token
            "shockers": {},  # Shocker ID to group mapping {"shocker_id": "group_name"}
            "openshock_url": "https://api.openshock.app"  # OpenShock API base URL
        }
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default_config
    return default_config


def save_app_config(config):
    """Save application configuration to config.json"""
    config_file = "app_config.json"
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"Failed to save config: {e}")


def extract_placeholders(messages):
    placeholders = set()
    for message in messages:
        try:
            placeholders.update(
                name for _, name, _, _ in string.Formatter().parse(message) if name
            )
        except Exception:
            continue
    return list(placeholders)


message_config = {
    "time": {
        "messages": [
            "{time}",
        ],
    },
    "boops": {
        "messages": [
            "Boops: {daily_boops} ᵗᵒᵈᵃʸ ({total_boops} ᵗᵒᵗᵃˡ)",
        ],
    },
    "joinmymusic_info": {
        "messages": [
            "JoinMyMusic.com",
        ],
    },
    "joinmymusic_artist": {
        "messages": [
            "{jmm_artist}",
        ],
    },
    "joinmymusic_song": {
        "messages": [
            "{jmm_song}",
        ],
    },
    "shock_info": {
        "messages": [
            "⚡ Shock: {shock_intensity}% ({shock_group})",
        ],
    },
}

all_messages = [
    msg for config in message_config.values() for msg in config.get("messages", [])
]
message_config["placeholders"] = extract_placeholders(all_messages)
