import os
import threading
import asyncio
import json
import requests
from time import sleep
from dotenv import load_dotenv
from aiohttp import web, WSMsgType

# --- Global Variables ---
HTTP_PORT = 3000
session_active = False
connected_clients = set()
main_loop = None

# --- Load Environment Variables ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in the .env file")


# --- Preserve the fetch_ephemeral_key Method ---
def fetch_ephemeral_key():
    instructions = "You are a friendly assistant to a 13-year old named Neev. Use gen-Alpha occasionally."
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-mini-realtime-preview-2024-12-17",
            "voice": "alloy",
            "input_audio_format": "pcm16",
            "input_audio_transcription": {"model": "whisper-1"},
            "instructions": instructions
        }
        resp = requests.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers=headers,
            json=payload,
        )
        if resp.status_code != 200:
            print("Failed to create ephemeral session:", resp.text)
            return None
        data = resp.json()
        return data["client_secret"]["value"]
    except Exception as e:
        print("Error fetching ephemeral key:", e)
        return None


# --- Broadcast Message Functions ---
def broadcast_message(msg_dict):
    """Schedule a broadcast of a JSON message to all connected WebSocket clients."""
    print(f"Broadcasting message: {msg_dict}")
    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(_async_broadcast(json.dumps(msg_dict)), main_loop)
    else:
        print("main_loop is not set. Cannot broadcast message.")


async def _async_broadcast(text_data):
    """Send the provided text data to every connected client."""
    print("Broadcasting message to all clients...")
    for ws in list(connected_clients):
        if not ws.closed:
            try:
                print(f"Sending '{text_data}' to client: {ws._req.remote}")
                await ws.send_str(text_data)
            except Exception as e:
                print("Error sending to client:", e)
                connected_clients.discard(ws)
        else:
            connected_clients.discard(ws)
            print("Client disconnected.")


# --- Session Toggle (Button Press) ---
def on_button_press():
    """Toggle the session state and broadcast the appropriate message."""
    global session_active
    print("Button pressed (simulated)!")
    if not session_active:
        session_active = True
        ephemeral_key = fetch_ephemeral_key()
        broadcast_message({
            "type": "start_session",
            "ephemeralKey": ephemeral_key
        })
        print("Session started.")
    else:
        session_active = False
        broadcast_message({"type": "end_session"})
        print("Session ended.")


# --- HTTP and WebSocket Handlers using aiohttp ---
async def index_handler(request):
    """Serve the index.html file when the root URL is requested."""
    return web.FileResponse('index.html')


async def websocket_handler(request):
    """Handle WebSocket connections."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    connected_clients.add(ws)
    print(f"New WebSocket connection from {request.remote}")
    print(f"Total connected clients: {len(connected_clients)}")

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "page_loaded":
                        print("Page loaded")
                    elif data.get("type") == "power_down":
                        print("Powering down..")
                except json.JSONDecodeError:
                    print("Received non-JSON message:", msg.data)
            elif msg.type == WSMsgType.ERROR:
                print("WebSocket connection error:", ws.exception())
    except Exception as e:
        print("WebSocket handler exception:", e)
    finally:
        connected_clients.discard(ws)
        print(f"Client {request.remote} disconnected. Total connected clients: {len(connected_clients)}")
    return ws





# --- App Startup Callback ---
async def on_startup(app):
    global main_loop
    main_loop = asyncio.get_running_loop()
    print("Startup complete. main_loop is set.")


async def start_keyboard_listener(app):
    print("Starting keyboard listener after server startup...")

    # --- Keyboard Listener ---
    def keyboard_listener():
        sleep(2)    # Sleep for 2 seconds to allow the server to start.
        while True:
            input("Press Enter to toggle session...")
            on_button_press()

    threading.Thread(target=keyboard_listener, daemon=True).start()


def main():
    # Create the aiohttp web application.
    app = web.Application()
    app.on_startup.append(on_startup)  # Your existing startup tasks.
    app.on_startup.append(start_keyboard_listener)  # Start keyboard listener here.

    app.router.add_get('/', index_handler)
    app.router.add_get('/ws', websocket_handler)

    print(f"Server starting on port {HTTP_PORT} (HTTP & WebSocket)...")
    web.run_app(app, port=HTTP_PORT)


if __name__ == "__main__":
    main()