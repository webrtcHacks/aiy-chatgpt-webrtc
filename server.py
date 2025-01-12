import os
import threading
import requests
from time import sleep
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file
from gpiozero import PWMLED, Button
import subprocess


chromium_process = None

###################################
#           LED + Button          #
###################################

# GPIO pins for LED and button
LED_PIN = 25
BUTTON_PIN = 23

# Create objects for LED and button
led = PWMLED(LED_PIN)
button = Button(BUTTON_PIN)

# Possible modes: "blinking" or "pulsing"
led_mode = "blinking"


def run_led():
    """
    Runs in a loop on a separate thread.
    Checks `led_mode` and updates the LED pattern accordingly.
    """
    global led_mode

    while True:
        if led_mode == "blinking":
            # Slow blink: LED on for 1 second, off for 1 second.
            led.on()
            sleep(1)
            if led_mode != "blinking":
                continue  # If mode changed mid-sleep, go back to top of loop
            led.off()
            sleep(1)
            # loop repeats as long as led_mode is "blinking"

        elif led_mode == "pulsing":
            # Pulse loop: fade in and out
            for brightness in range(0, 101, 5):  # Fade in
                if led_mode != "pulsing":
                    break  # If mode changed, break
                led.value = brightness / 100.0
                sleep(0.05)

            if led_mode != "pulsing":
                continue  # Check again if mode changed

            for brightness in range(100, -1, -5):  # Fade out
                if led_mode != "pulsing":
                    break
                led.value = brightness / 100.0
                sleep(0.05)
            # loop repeats as long as led_mode is "pulsing"


def on_button_press():
    """
    Toggles between blinking and pulsing.
    Also launches Chromium on the first press (pulsing),
    and terminates Chromium on the second press (blinking).
    """
    global led_mode, chromium_process
    print("Button pressed!")

    if led_mode == "blinking":
        # Switch to pulsing, launch Chromium
        led_mode = "pulsing"
        print("Switching LED mode to pulsing. Launching Chromium...")
        chromium_process = subprocess.Popen([
            "chromium-browser",
            "--disable-gpu",
            "--autoplay-policy=no-user-gesture-required",
            "--enable-speech-dispatcher",
            "--allow-insecure-localhost",
            "--use-fake-ui-for-media-stream",
            "--unsafely-treat-insecure-origin-as-secure=http://localhost:3000",
            # "--alsa-input-device=hw:0,0",
            # "--alsa-output-device=hw:0,0",
            "http://localhost:3000"  # The page that runs your assistant
        ])
    else:
        # Switch to blinking, terminate Chromium
        led_mode = "blinking"
        print("Switching LED mode to blinking. Terminating Chromium...")
        if chromium_process is not None:
            chromium_process.terminate()
            chromium_process = None


# Attach button press handler
button.when_pressed = on_button_press

###################################
#           Flask Server          #
###################################
app = Flask(__name__)

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in the .env file")

PORT = 3000


# Serve files
@app.route("/<filename>", methods=["GET"])
def serve_audio(filename):
    if filename.endswith(".wav"):
        return send_file(filename)
    else:
        return jsonify({"error": "File not found"}), 404


@app.route("/session", methods=["GET"])
def generate_session():
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-realtime-preview-2024-12-17",
            "voice": "alloy",
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "instructions": "You are a friendly assistant to a 13-year old named Neev. "
                            "Use gen-Alpha language occasionally, but mostly be professional and helpful. "
                            "Inject emotion into your voice where appropriate. "

        }
        response = requests.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers=headers,
            json=payload,
        )

        if response.status_code != 200:
            error_details = response.text
            print(f"Failed to fetch session: {error_details}")
            return jsonify({"error": "Failed to create session", "details": error_details}), response.status_code

        # Return the response from OpenAI
        return jsonify(response.json()), 200
    except Exception as e:
        print(f"Error during /session request: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/ready", methods=["GET"])
def check_ready():
    return jsonify({"ready": True}), 200

@app.route("/", methods=["GET"])
def serve_index():
    return send_file("index.html")


###################################
#              Main               #
###################################
if __name__ == "__main__":
    # Start LED thread
    led_thread = threading.Thread(target=run_led, daemon=True)
    led_thread.start()

    os.environ["DISPLAY"] = ":0"    # needed for the Chromium browser

    try:
        # Start Flask server
        print(f"Server is running on http://localhost:{PORT}")
        app.run(host="0.0.0.0", port=PORT)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        led.off()
        # If Chromium is still running, terminate it
        if chromium_process is not None:
            chromium_process.terminate()
