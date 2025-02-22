import os
import threading
import asyncio
import json
from time import sleep
from aiohttp import web, WSMsgType

# --- Global Variables ---
HTTP_PORT = 3000
connected_clients = set()
main_loop = None


# --- Broadcast Message Functions ---
def broadcast_message(msg_dict):
    """Schedule a broadcast of a JSON message to all connected WebSocket clients."""
    print(f"Broadcasting message: {msg_dict}")
    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(_async_broadcast(json.dumps(msg_dict)), main_loop)
    else:
        print("main_loop is not set. Cannot broadcast message.")

#
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
    print("Button pressed (simulated)!")
    broadcast_message({
        "type": "button_press",
    })


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
                        print("User asked to power down..")
                        # os.system("sudo shutdown now")
                    elif data.get("type") == "end_session":
                        print("User asked to end session..")
                    else:
                        print("Received unknown message:", data)
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