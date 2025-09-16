import string
import json
import os


def get_default_message_config():
    """Get default message configuration"""
    return {
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
                "⚡ Shock: {shock_intensity}% {shock_duration} ({shock_group})",
            ],
        },
        "internet_shock_info": {
            "messages": [
                "⚡ {internet_shock_intensity}% {internet_shock_duration} {internet_shock_user} ({internet_shock_shocker})",
            ],
        },
    }

def load_app_config():
    """Load application configuration from config.json"""
    config_file = "app_config.json"
    default_config = {
        "show_music": True,
        "messages": get_default_message_config(),
        "shockosc": {
            "enabled": False,
            "mode": "static",  # "static" or "random"
            "static_intensity": 20,  # 0-100
            "random_min": 30,  # 0-100
            "random_max": 70,  # 0-100
            "duration": 1.0,  # 0.3-30.0 seconds
            "groups": ["leftleg", "rightleg"],  # ShockOSC groups to control
            "show_shock_info": True,  # Show shock percentage in chatbox
            "cooldown_delay": 3.0,  # Cooldown delay in seconds (0.0-60.0)
            "hold_time": 0.1,  # Required contact hold time in seconds (0.0-5.0)
            "openshock_token": "",  # OpenShock API token
            "shockers": {},  # Shocker ID to group mapping {"shocker_id": "group_name"}
            "openshock_url": "https://api.openshock.app",  # OpenShock API base URL
            "show_internet_shocks": True  # Show shocks from internet users in chatbox
        }
    }

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                user_config = json.load(f)

                # Merge with defaults to ensure all required fields exist
                merged_config = default_config.copy()
                merged_config.update(user_config)

                # Ensure messages section exists and merge with defaults
                if "messages" not in merged_config:
                    merged_config["messages"] = get_default_message_config()
                else:
                    # Merge user messages with defaults to ensure all message types exist
                    default_messages = get_default_message_config()
                    for key, value in default_messages.items():
                        if key not in merged_config["messages"]:
                            merged_config["messages"][key] = value

                return merged_config
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


def reload_message_config():
    """Reload message configuration from the config file"""
    global message_config
    _app_config = load_app_config()
    message_config = _app_config.get("messages", get_default_message_config())

    all_messages = [
        msg for config in message_config.values() for msg in config.get("messages", [])
    ]
    message_config["placeholders"] = extract_placeholders(all_messages)

# Load configuration and set up message_config
_app_config = load_app_config()
message_config = _app_config.get("messages", get_default_message_config())

all_messages = [
    msg for config in message_config.values() for msg in config.get("messages", [])
]
message_config["placeholders"] = extract_placeholders(all_messages)
