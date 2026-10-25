# MCP MIDI Server

A FastMCP Server which allows an LLM to send MIDI sequences into any software that supports MIDI input.

## Features

- Creates a virtual MIDI output port
- Sends MIDI Note On/Off messages
- Sends Control Change (CC) messages
- Sequences MIDI events with precise timing
- Can be used as a MIDI input device in any application that supports MIDI

## Requirements

- Python 3.7+
- rtmidi (built with both ALSA seq and JACK support on Linux)
- fastmcp 4.x (the pinned `requirements.txt` targets fastmcp 2.x, whose `pydantic_core` has no Python 3.14 wheels and whose API differs from 4.x — see "Notes" below)
- python-dotenv
- asyncio

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd mcp-server-midi
   ```

2. Create a virtual env, activate it and install dependencies:
   ```
   python -m venv .venv
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

   On Python 3.14+ (or if the pinned `requirements.txt` fails to build), install with relaxed pins instead:
   ```
   pip install --upgrade python-rtmidi fastmcp python-dotenv
   ```

   On Linux, `python-rtmidi`'s JACK support requires `libjack` headers at build time (provided by `pipewire-jack` / `jack2` depending on distro). ALSA seq support requires `alsa-lib` headers.

3. Create a `.env` file with your configuration:
   ```
   PORT=8123
   MIDI_API=jack   # or "alsa" — see "MIDI API" below
   ```

## MIDI API

On Linux the server can create its virtual port via either the **JACK** API or the **ALSA sequencer** API. Set `MIDI_API` in `.env` (or the environment) to choose:

- `MIDI_API=jack` (default) — opens a JACK MIDI port. Use this if your DAW is a JACK client (e.g. REAPER running under PipeWire-JACK, Bitwig, Ardour with JACK). The port appears in the JACK/PipeWire graph as `RtMidiOut Client:MCP MIDI Out`.
- `MIDI_API=alsa` — opens an ALSA sequencer port. Use this if your DAW reads ALSA seq directly (e.g. REAPER configured for ALSA MIDI, or non-JACK Linux audio setups). The port appears in `/proc/asound/seq/clients` as `MCP MIDI Out` (client `RtMidiOut Client`).

If `MIDI_API=jack` is requested but the JACK server is unavailable, the server falls back to ALSA seq automatically.

## Usage

Run the server:

```
python mcp_midi_server.py
```

The server creates a virtual MIDI port named "MCP MIDI Out" that can be used as a MIDI input device in other applications. This means you can:

- Connect digital audio workstations (DAWs) like Ableton Live, Logic Pro, FL Studio, REAPER, or Bitwig to receive MIDI from this server
- Use the server to control hardware synthesizers through your computer's MIDI interface
- Connect to any other software that accepts MIDI input (virtual instruments, lighting controllers, etc.)

Simply select "MCP MIDI Out" as a MIDI input device in your preferred MIDI-compatible application.

## Notes for fastmcp 4.x

The upstream `mcp_midi_server.py` was written for fastmcp 2.x, which used a `settings={"port": ...}` kwarg on `FastMCP()`. fastmcp 4.x removed that kwarg; this fork passes the port to `mcp.run(transport='sse', port=...)` instead. If you reinstall against the pinned `requirements.txt` (fastmcp 2.1.2), revert this change or pin fastmcp to a 4.x release.

## MCP Config

The server uses Server-Sent Events (SSE), this is how to config it in Cursor:
```
{
  "mcpServers": {
      "midi": {
          "url": "http://localhost:8123/sse"
      }
   }
}
```

## API Methods

### Send Note On

Sends a MIDI Note On message.

Parameters:
- `note`: MIDI note number (0-127)
- `velocity`: Note velocity (0-127, default 127)
- `channel`: MIDI channel (0-15, default 0)

### Send Note Off

Sends a MIDI Note Off message.

Parameters:
- `note`: MIDI note number (0-127)
- `velocity`: Note off velocity (0-127, default 64)
- `channel`: MIDI channel (0-15, default 0)

### Send Control Change

Sends a MIDI Control Change (CC) message.

Parameters:
- `controller`: CC controller number (0-127)
- `value`: CC value (0-127)
- `channel`: MIDI channel (0-15, default 0)

### Send MIDI Sequence

Sends a sequence of MIDI Note On/Off messages with specified durations.

Parameters:
- `events`: A list of event dictionaries. Each dictionary must contain:
  - `note`: MIDI note number (0-127)
  - `velocity`: Note velocity (0-127, default 127)
  - `channel`: MIDI channel (0-15, default 0)
  - `duration`: Time in seconds to hold the note before sending Note Off
  - `start_time`: Time in seconds when to start the note, relative to sequence start (default 0)

## Example

Using the API to play a C major chord:

```python
events = [
    {"note": 60, "velocity": 100, "duration": 1.0, "start_time": 0.0},  # C4
    {"note": 64, "velocity": 100, "duration": 1.0, "start_time": 0.0},  # E4
    {"note": 67, "velocity": 100, "duration": 1.0, "start_time": 0.0},  # G4
]
# Send to the MCP MIDI Server API
```

## License

MIT