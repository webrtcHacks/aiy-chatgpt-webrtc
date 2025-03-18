import os
import threading
import json
import subprocess
import asyncio
from time import sleep
from gpiozero import PWMLED, Button
from aiohttp import web, WSMsgType

#######################################
# Configuration and Global State
#######################################
PORT = 3000
LED_PIN = 25
BUTTON_PIN = 23

led = PWMLED(LED_PIN)
button = Button(BUTTON_PIN)

led_mode = "waiting"  # Start with LED in "waiting" state
session_active = False

connected_clients = set()
main_loop = None  # Store main event loop here

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
            sleep(3)
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
            return

#######################################
# Broadcast to All Connected Clients
#######################################
def broadcast_message(msg_dict):
    text_data = json.dumps(msg_dict)
    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(_async_broadcast(text_data), main_loop)
    else:
        print("Warning: main_loop not initialized; cannot broadcast.")

async def _async_broadcast(text_data):
    global led_mode
    if not connected_clients:
        led_mode = "error"
        return
    to_remove = []
    for ws in list(connected_clients):
        if not ws.closed:
            try:
                await ws.send_str(text_data)
            except Exception as e:
                print("Error sending to client:", e)
                led_mode = "error"
                to_remove.append(ws)
        else:
            to_remove.append(ws)
    for ws in to_remove:
        connected_clients.discard(ws)

#######################################
# Button Press Callback
#######################################
def on_button_press():
    global session_active, led_mode
    print("Button pressed!")
    if not session_active:
        session_active = True
        led_mode = "active"
        broadcast_message({
            "type": "start_session",
        })
        print("Session started, LED pulsing.")
    else:
        session_active = False
        led_mode = "waiting"
        broadcast_message({
            "type": "end_session"
        })
        print("Session ended, LED blinking.")

#######################################
# HTTP Request Handler (Serving index.html)
#######################################
async def index_handler(request):
    return web.FileResponse('index.html')

#######################################
# WebSocket Handler
#######################################
async def websocket_handler(request):
    global session_active, led_mode
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    connected_clients.add(ws)
    print(f"New WebSocket connection from {request.remote}")
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "page_loaded":
                        print("Page loaded")
                        led_mode = "waiting"
                    elif data.get("type") == "start_session":
                        print("Start session received via websocket.")
                        session_active = True
                        led_mode = "active"
                    elif data.get("type") == "end_session":
                        print("End session received via websocket.")
                        session_active = False
                        led_mode = "waiting"
                    elif data.get("type") == "shut_down":
                        print("Shutdown received via websocket.")
                        led_mode = "off"
                        asyncio.get_running_loop().stop()
                        print("Shutting down in 5 seconds...")
                        sleep(5)
                        os.system("sudo poweroff")

                except json.JSONDecodeError:
                    print("Received non-JSON message:", msg.data)
            elif msg.type == WSMsgType.ERROR:
                print("WebSocket connection error:", ws.exception())
    except Exception as e:
        print("WebSocket handler exception:", e)
    finally:
        connected_clients.discard(ws)
        print(f"Client {request.remote} disconnected.")
    return ws

#######################################
# App Startup Callback
#######################################
async def on_startup(app):
    global main_loop
    main_loop = asyncio.get_running_loop()
    print("Startup complete. main_loop is set.")

#######################################
# Main Entry Point
#######################################
def main():
    # Start LED thread
    led_thread = threading.Thread(target=run_led, daemon=True)
    led_thread.start()

    # Launch Chromium
    os.environ["DISPLAY"] = ":0"
    chrome_args = [
        "chromium-browser",
        "--no-first-run",
        "--disable-gpu",
        "--autoplay-policy=no-user-gesture-required",
        "--allow-insecure-localhost",
        "--disable-infobars",
        "--use-fake-ui-for-media-stream",
        "--disable-session-crashed-bubble",
        "--unsafely-treat-insecure-origin-as-secure=http://localhost:3000",
        "--auto-open-devtools-for-tabs",
        "--enable-logging",
        f"--log-file={os.path.expanduser('~/chromium.log')}",
        "--v=1",
        f"http://localhost:{PORT}"
    ]
    with open(os.path.expanduser('~/chromium_output.log'), 'w') as output_file:
        chromium_process = subprocess.Popen(chrome_args, stdout=output_file, stderr=output_file)
        print("Chromium launched...")

    # Create aiohttp application with routes
    app = web.Application()
    app.on_startup.append(on_startup)
    app.router.add_get('/', index_handler)
    app.router.add_get('/ws', websocket_handler)

    # Attach button callback
    button.when_pressed = on_button_press

    print(f"Server starting on port {PORT} (HTTP & WebSocket)...")
    try:
        web.run_app(app, port=PORT)
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print("Main loop error:", e)
    finally:
        led.off()
        if chromium_process:
            chromium_process.terminate()

if __name__ == "__main__":
    main()
