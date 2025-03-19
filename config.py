import string


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
}

all_messages = [
    msg for config in message_config.values() for msg in config.get("messages", [])
]
message_config["placeholders"] = extract_placeholders(all_messages)
