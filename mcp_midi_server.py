import os
import rtmidi
import asyncio
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

# --- MIDI Setup ---
# rtmidi API selection. Default to ALSA seq on Linux so the virtual port can
# be bridged into JACK MIDI by a2jmidid (which exposes ALSA seq ports as JACK
# MIDI ports that JACK-based DAWs like REAPER can see). Override with
# MIDI_API=jack in .env if you want a native JACK port instead (note: REAPER
# under PipeWire-JACK filters out non-physical JACK MIDI ports, so the ALSA
# + a2jmidid path is the one that actually shows up in REAPER).
midi_api_name = os.getenv("MIDI_API", "alsa").lower()
if midi_api_name == "jack":
    try:
        midiout = rtmidi.MidiOut(rtmidi.API_UNIX_JACK)
        print("Using JACK MIDI API")
    except Exception as e:
        print(f"JACK API unavailable ({e}), falling back to ALSA seq")
        midiout = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA)
else:
    midiout = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA)
    print("Using ALSA seq MIDI API")

available_ports = midiout.get_ports()

# Create a virtual MIDI port
port_name = "MCP MIDI Out"
try:
    midiout.open_virtual_port(port_name)
    print(f"Opened virtual MIDI port: {port_name}")
except rtmidi.RtMidiError as e:
    print(f"Error opening virtual MIDI port: {e}")
    # Handle error appropriately, maybe exit or fallback
    exit()

# --- MCP Server Setup ---
# fastmcp 4.x removed the settings= kwarg; port is passed to mcp.run() below.
mcp = FastMCP(
    name="MCP MIDI Server",
    instructions="Sends MIDI commands received via MCP.",
)

# --- MCP Methods ---
# We will define methods here to handle MIDI messages


# Example: Send Note On
@mcp.tool()
async def send_note_on(
    note: int,
    velocity: int = 127,
    channel: int = 0
):
    """Sends a MIDI Note On message.

    Args:
        note: MIDI note number (0-127).
        velocity: Note velocity (0-127, default 127).
        channel: MIDI channel (0-15, default 0).
    """
    if not 0 <= note <= 127:
        raise ValueError("Note must be between 0 and 127")
    if not 0 <= velocity <= 127:
        raise ValueError("Velocity must be between 0 and 127")
    if not 0 <= channel <= 15:
        raise ValueError("Channel must be between 0 and 15")

    # MIDI Note On status byte: 0x90 | channel
    status = 0x90 | channel
    message = [status, note, velocity]
    midiout.send_message(message)
    msg = f"Sent Note On: ch={channel}, note={note}, vel={velocity}"
    print(msg)
    return {"status": "success", "message": msg}


# Example: Send Note Off
@mcp.tool()
async def send_note_off(
    note: int,
    velocity: int = 64,
    channel: int = 0
):
    """Sends a MIDI Note Off message.

    Args:
        note: MIDI note number (0-127).
        velocity: Note off velocity (0-127, default 64).
        channel: MIDI channel (0-15, default 0).
    """
    if not 0 <= note <= 127:
        raise ValueError("Note must be between 0 and 127")
    if not 0 <= velocity <= 127:
        raise ValueError("Velocity must be between 0 and 127")
    if not 0 <= channel <= 15:
        raise ValueError("Channel must be between 0 and 15")

    # MIDI Note Off status byte: 0x80 | channel
    status = 0x80 | channel
    message = [status, note, velocity]
    midiout.send_message(message)
    msg = f"Sent Note Off: ch={channel}, note={note}, vel={velocity}"
    print(msg)
    return {"status": "success", "message": msg}


# Example: Send Control Change
@mcp.tool()
async def send_control_change(
    controller: int,
    value: int,
    channel: int = 0
):
    """Sends a MIDI Control Change (CC) message.

    Args:
        controller: CC controller number (0-127).
        value: CC value (0-127).
        channel: MIDI channel (0-15, default 0).
    """
    if not 0 <= controller <= 127:
        raise ValueError("Controller number must be between 0 and 127")
    if not 0 <= value <= 127:
        raise ValueError("Value must be between 0 and 127")
    if not 0 <= channel <= 15:
        raise ValueError("Channel must be between 0 and 15")

    # MIDI CC status byte: 0xB0 | channel
    status = 0xB0 | channel
    message = [status, controller, value]
    midiout.send_message(message)
    msg = f"Sent CC: ch={channel}, cc={controller}, val={value}"
    print(msg)
    return {"status": "success", "message": msg}


# --- New Tool: Send MIDI Sequence ---
@mcp.tool()
async def send_midi_sequence(events: list):
    """Sends a sequence of MIDI Note On/Off messages with specified durations.

    Args:
        events: A list of event dictionaries. Each dictionary must contain:
            - note: MIDI note number (0-127).
            - velocity: Note velocity (0-127, default 127).
            - channel: MIDI channel (0-15, default 0).
            - duration: Time in seconds to hold the note before sending
              Note Off (float).
            - start_time: Time in seconds when to start the note,
              relative to sequence start (default 0).
    """
    # Start time reference for the entire sequence
    sequence_start = asyncio.get_event_loop().time()
    tasks = []
    results = []

    for i, event in enumerate(events):
        note = event.get("note")
        velocity = event.get("velocity", 127)
        channel = event.get("channel", 0)
        duration = event.get("duration")
        start_time = event.get("start_time", 0)

        # --- Input Validation ---
        error_prefix = f"Event {i}:"
        if note is None:
            raise ValueError(f"{error_prefix} 'note' is required.")
        if duration is None:
            raise ValueError(f"{error_prefix} 'duration' is required.")
        if not isinstance(note, int) or not 0 <= note <= 127:
            raise ValueError(
                f"{error_prefix} Note must be an integer between 0 and 127"
            )
        if not isinstance(velocity, int) or not 0 <= velocity <= 127:
            raise ValueError(
                f"{error_prefix} Velocity must be an integer between 0 and 127"
            )
        if not isinstance(channel, int) or not 0 <= channel <= 15:
            raise ValueError(
                f"{error_prefix} Channel must be an integer between 0 and 15"
            )
        if not isinstance(duration, (int, float)) or duration < 0:
            raise ValueError(
                f"{error_prefix} Duration must be a non-negative number"
            )
        if not isinstance(start_time, (int, float)) or start_time < 0:
            raise ValueError(
                f"{error_prefix} start_time must be a non-negative number"
            )

        # Create async task for this note
        task = asyncio.create_task(
            play_note_with_timing(
                note, velocity, channel, duration, start_time, 
                sequence_start, i, results
            )
        )
        tasks.append(task)

    # Wait for all notes to complete
    if tasks:
        await asyncio.gather(*tasks)

    num_events = len(events)
    success_msg = f"Successfully processed {num_events} events."
    return {
        "status": "success",
        "message": success_msg,
        "results": results
    }


async def play_note_with_timing(
    note, velocity, channel, duration, start_time, 
    sequence_start, event_index, results
):
    """Helper function to play a single note with proper timing."""
    # Calculate absolute times
    now = asyncio.get_event_loop().time()
    time_elapsed = now - sequence_start

    # Wait until it's time to start this note
    if start_time > time_elapsed:
        await asyncio.sleep(start_time - time_elapsed)

    # Send Note On
    try:
        status_on = 0x90 | channel
        message_on = [status_on, note, velocity]
        midiout.send_message(message_on)
        on_msg = f"Sent Note On: ch={channel}, note={note}, vel={velocity}"
        print(on_msg)
        results.append({
            "status": "note_on_sent", 
            "message": on_msg,
            "event_index": event_index
        })

        # Wait for the note duration
        await asyncio.sleep(duration)

        # Send Note Off
        status_off = 0x80 | channel
        message_off = [status_off, note, 0]  # Note Off with velocity 0
        midiout.send_message(message_off)
        off_msg = f"Sent Note Off: ch={channel}, note={note}"
        print(off_msg)
        results.append({
            "status": "note_off_sent", 
            "message": off_msg,
            "event_index": event_index
        })
    except Exception as e:
        error_msg = f"Event {event_index}: Error processing event: {e}"
        print(error_msg)
        results.append({
            "status": "error",
            "message": error_msg,
            "event_index": event_index
        })


# --- Main Execution ---
if __name__ == "__main__":
    # Ensure MIDI port is closed properly on exit
    import atexit
    atexit.register(midiout.close_port)

    port = os.getenv("PORT", "8123")
    mcp.run(transport='sse', port=int(port))
    # This part might not be reached if server.run() blocks indefinitely
    # Consider running the server in a separate thread if needed
    # Cleanup is handled by atexit
    # print("Closing MIDI port...")
    # midiout.close_port()
    # print("Server stopped.")
