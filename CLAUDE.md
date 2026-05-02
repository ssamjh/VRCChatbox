# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# GUI mode
python app.py --gui

# Headless mode
python app.py

# Windows launcher
start.bat
```

**Dependencies** (no requirements.txt — install manually):
```bash
pip install python-osc PyQt6 requests websockets
```

**OSC monitoring tool** (useful for debugging VRChat avatar parameters):
```bash
python test.py
```

## Architecture

This is a Python desktop app that displays real-time data in the VRChat in-game chatbox via OSC (Open Sound Control) and integrates with OpenShock for haptic feedback.

### Module Overview

| File | Role |
|------|------|
| `app.py` | `VRChatMessenger` — main orchestrator, OSC server, message scheduling |
| `shockosc.py` | `ShockOSCController` — OpenShock API, group cooldowns, SignalR real-time events |
| `slide.py` | `SlideController` — OSC variable monitoring, probability/hold-mode shock triggering |
| `gui.py` | PyQt6 settings UI — three pages: General, ShockOSC, Slide |
| `placeholders.py` | `DataCache` singleton + `get_placeholder_value()` — feeds live data into message templates |
| `config.py` | Load/save `app_config.json`; also owns `message_config` for the rotating message system |
| `boop_counter.py` | Persistent daily/total boop counter backed by `boops.json` |

### Key Data Flow

1. **VRChat → App**: OSC server on port 9001 receives avatar parameter updates (`/avatar/parameters/...`)
2. **App → VRChat**: Chatbox messages sent to OSC port 9000 via `/chatbox/input`
3. **Slide mode**: `SlideController` subscribes to OSC paths via `dispatcher.map()`; polls cached values every `poll_interval` seconds; fires OpenShock API when probability/hold conditions are met
4. **Message display**: `VRChatMessenger` rotates through `active_messages` dict, rate-limited to 1.5s minimum, updating only on change or when forced

### Configuration

All settings live in `app_config.json`. `config.py` merges it against defaults on load. The GUI calls `save_app_config()` and pushes updated dicts directly to the running controllers via `update_config()` — no restart needed.

**Message templates** use `{placeholder}` syntax. Available placeholders: `{time}`, `{daily_boops}`, `{total_boops}`, `{jmm_artist}`, `{jmm_song}`, `{shock_intensity}`, `{shock_group}`, `{shock_duration}`, `{internet_shock_intensity}`, `{internet_shock_duration}`, `{internet_shock_user}`, `{internet_shock_shocker}`.

### Shocker / Cooldown Model

- Shockers are identified by OpenShock UUID; each has a `group` name (e.g. `leftleg`, `rightleg`)
- **Group cooldown** (in `shockosc.py`): prevents re-shocking the same group too quickly; also broadcasts `/avatar/parameters/ShockOsc/{group}_Cooldown` bool to VRChat for avatar animations
- **Slide cooldown** (in `slide.py`): per-shocker, random duration between `cooldown_min` and `cooldown_max`; hold mode bypasses this
- Hold mode (`skip_cooldown=True`) bypasses slide cooldowns; group cooldowns still apply

### Threading

- OSC server: daemon thread
- Slide polling: daemon thread (restarts on config change)
- JoinMyMusic SSE: daemon thread in `DataCache`
- OpenShock SignalR: asyncio event loop in its own thread
- All cooldown timers: `threading.Timer`
- Shared OSC value cache in `slide.py` protected by `values_lock`
