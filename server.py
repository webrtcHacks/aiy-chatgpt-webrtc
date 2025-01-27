import os
import threading
import requests
from time import sleep
from dotenv import load_dotenv
from gpiozero import PWMLED, Button
import asyncio
import websockets
import json
import subprocess

#######################################
# Configuration and Global State
#######################################
HTTP_PORT = 3000
WS_PORT = 3001

LED_PIN = 25
BUTTON_PIN = 23

led = PWMLED(LED_PIN)
button = Button(BUTTON_PIN)

led_mode = "waiting"  # Start with LED in "waiting" state
session_active = False

connected_clients = set()
main_loop = None  # We'll store the main event loop here

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in the .env file")


#######################################
# LED Behavior Thread
#######################################
def run_led():
    global led_mode
    while True:
        if led_mode == "waiting":
            led.on()
            sleep(1)
            if led_mode != "waiting":
                continue
            led.off()
            sleep(1)
        elif led_mode == "error":
            led.on()
            sleep(0.5)
            if led_mode != "error":
                continue
            led.off()
            sleep(0.5)
        elif led_mode == "active":
            for brightness in range(0, 101, 5):
                if led_mode != "active":
                    break
                led.value = brightness / 100.0
                sleep(0.05)
            if led_mode != "active":
                continue
            for brightness in range(100, -1, -5):
                if led_mode != "active":
                    break
                led.value = brightness / 100.0
                sleep(0.05)
        elif led_mode == "off":
            led.off()
            sleep(1)
        else:
            print("ERROR: unknown LED mode:", led_mode)
            return  # Exit thread


#######################################
# Button Press Callback
#######################################
def on_button_press():
    global session_active, led_mode
    print("Button pressed!")

    if not session_active:
        # Start session
        session_active = True
        led_mode = "active"
        ephemeral_key = fetch_ephemeral_key()
        broadcast_message({
            "type": "start_session",
            "ephemeralKey": ephemeral_key
        })
        print("Session started, LED pulsing.")
    else:
        # End session
        session_active = False
        led_mode = "waiting"
        broadcast_message({
            "type": "end_session"
        })
        print("Session ended, LED blinking.")


#######################################
# Fetch Ephemeral Key from OpenAI
#######################################
def fetch_ephemeral_key():
    global led_mode
    instructions = ("You are a friendly assistant to a 13-year old named Neev. "
                    "Use gen-Alpha language occasionally, but mostly be professional and helpful. ")

    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-realtime-preview-2024-12-17",
            "voice": "alloy",
            "input_audio_transcription": {"model": "whisper-1"},
            "instructions": instructions,
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
        led_mode = "error"
        return None


#######################################
# Broadcast to All Connected Clients
#######################################
def broadcast_message(msg_dict):
    """
    Called from the button callback (or elsewhere).
    We push a coroutine to the *main event loop* using run_coroutine_threadsafe.
    """
    text_data = json.dumps(msg_dict)
    # Use the main_loop we stored in main()
    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(_async_broadcast(text_data), main_loop)
    else:
        print("Warning: main_loop is not initialized yet; cannot broadcast.")


async def _async_broadcast(text_data):
    """
    Actually broadcast the message to each connected WebSocket.
    Must run in the main event loop context.
    """
    global led_mode

    if not connected_clients:
        led_mode = "error"
        return
    to_remove = []
    for ws in connected_clients:
        if ws.open:
            try:
                await ws.send(text_data)
            except Exception as e:
                print("Error sending to client:", e)
                led_mode = "error"
                to_remove.append(ws)
        else:
            to_remove.append(ws)
    for ws in to_remove:
        connected_clients.discard(ws)


#######################################
# WebSocket Handler on port 3001
#######################################
async def handler(websocket, path):
    global led_mode
    print(f"New WebSocket connection from {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            if data.get("type") == "page_loaded":
                print("Page loaded")
                led_mode = "waiting"
    finally:
        connected_clients.discard(websocket)
        print(f"Client {websocket.remote_address} disconnected.")


#######################################
# Simple HTTP Server on port 3000
#######################################
def start_http_server():
    import http.server
    import socketserver

    global led_mode

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            if path == "/":
                path = "/index.html"
            return os.getcwd() + path

    httpd = socketserver.TCPServer(("", HTTP_PORT), Handler)
    print(f"HTTP server serving at port {HTTP_PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("HTTP server error:", e)
        led_mode = "error"
    finally:
        httpd.server_close()  # Ensures port is freed on exit


#######################################
# Main Entry Point
#######################################
def main():
    global main_loop
    global led_mode

    # 1) Start LED thread
    led_thread = threading.Thread(target=run_led, daemon=True)
    led_thread.start()

    # 2) Start HTTP server (serving index.html) in background
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    # 3) Launch Chromium
    os.environ["DISPLAY"] = ":0"
    chrome_args = [
        "chromium-browser",
        # "--kiosk",
        "--no-first-run",
        "--disable-gpu",
        "--autoplay-policy=no-user-gesture-required",
        "--allow-insecure-localhost",
        "--disable-infobars",
        "--use-fake-ui-for-media-stream",
        "--disable-session-crashed-bubble",
        "--auto-open-devtools-for-tabs",
        "--unsafely-treat-insecure-origin-as-secure=http://localhost:3000",
        f"http://localhost:{HTTP_PORT}"
    ]
    chromium_process = subprocess.Popen(chrome_args)
    print("Chromium launched...")

    # 4) WebSocket server in the main thread / event loop
    loop = asyncio.get_event_loop()
    main_loop = loop  # store it in global variable so broadcast_message can use it

    ws_server = websockets.serve(handler, "0.0.0.0", WS_PORT)
    loop.run_until_complete(ws_server)
    print(f"WebSocket server running on port {WS_PORT}...")

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
        pass
    except Exception as e:
        print("Main loop error:", e)
        led_mode = "error"
    finally:
        led.off()
        if chromium_process:
            chromium_process.terminate()


# Attach button callback and run
button.when_pressed = on_button_press

if __name__ == "__main__":
    main()
