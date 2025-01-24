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
    "status": {
        "rotation_interval": 10,
        "messages": ["{time} - {heart_rate}bpm"],
    },
    "system": {
        "rotation_interval": 10,
        "messages": [
            "Watch 🔋: {watch_battery}%",
            "Phone 🔋: {phone_battery}%",
            "Temp: {room_temp}°C {room_temp_f}°F",
            "Humidity: {room_humid}%",
            "Light Level: {room_light}lux",
            "GPU: {gpu_temp}°C",
            "Daily Steps: {steps}",
            "IRL Location: {location}",
        ],
    },
    "joinmymusic_info": {
        "rotation_interval": 10,
        "messages": [
            "JoinMyMusic.com",
            "Live Radio Station",
            "I Take Song Requests",
        ],
    },
    "joinmymusic_np1": {
        "rotation_interval": 10,
        "messages": [
            "{jmm_song}",
        ],
    },
    "joinmymusic_np2": {
        "rotation_interval": 10,
        "messages": [
            "{jmm_artist}",
        ],
    },
}

all_messages = [
    msg for config in message_config.values() for msg in config.get("messages", [])
]
message_config["placeholders"] = extract_placeholders(all_messages)
