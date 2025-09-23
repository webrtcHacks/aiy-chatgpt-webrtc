# GPT Realtime WebRTC Demo

A lightweight, static, client‑side demo showing how to connect a browser directly to OpenAI's Realtime API over WebRTC for low‑latency, bi‑directional audio and video transmission. 
It is designed as an simple, educational reference. 
Vanilla JavaScript only inside a couple `<script>` tags inside a single HTML - no frameworks.

`index.html` runs the new gpt-realtime GA API.

`beta-api.html` uses the original realtime preview API.

## Further Reading / Background
For full context, protocol details, architectural breakdowns, and troubleshooting guidance, see these companion posts:
1. How OpenAI does WebRTC in the new GPT Realtime – https://webrtchacks.com/how-openai-does-webrtc-in-the-new-gpt-realtime/
2. The (Unofficial) Guide to the OpenAI Realtime WebRTC API – https://webrtchacks.com/the-unofficial-guide-to-openai-realtime-webrtc-api/


## Live Demo Pages
Hosted versions of this page on GitHub Pages:
- gpt-realtime: https://webrtchacks.github.io/gpt-realtime-webrtc
- Realtime preview/Beta: https://webrtchacks.github.io/gpt-realtime-webrtc/beta-api.html (source: `beta-api.html`)


## What This Project Shows
- Direct browser ↔ OpenAI Realtime API connection using WebRTC (no custom server in this repo)
- Creation and negotiation of a peer connection using an SDP offer/answer flow
- Outbound microphone capture and inbound synthesized audio playback
- Video capture and transmission (on _gpt-realtime_)
- Basic settings UI for pasting your own OpenAI API key and adjusting options
- A beta page for exploring new API fields / events as they appear

Supporting reference text diagrams:
- `webrtc-setup-uml.txt` – WebRTC setup sequence outline in the new gpt-realtime
- `flow-uml.txt` – high-level interaction / event flow for beta-api.html 

## Quick Start
Option A: Use GitHub Pages (fastest)
1. Open the main demo: https://webrtchacks.github.io/gpt-realtime-webrtc
2. Click the Settings button (gear icon) in the UI.
3. Paste an OpenAI API key that has Realtime API access.
4. Allow microphone access when prompted.
5. Start interacting (speak) and listen for low-latency responses.

Option B: Run locally (still static)
1. Clone this repo.
2. Just open `index.html` (or `beta-api.html`) directly in a modern Chromium-based browser or Firefox. (If your browser blocks local mic capture via file:// you can serve the folder with a simple static server, e.g. `python -m http.server`.)
3. Follow steps 2–5 above.

## IMPORTANT: API Key & Security Notes
This is a pure client-side demo. There is no backend here performing token exchange.

You must open the Settings dialog and paste your own OpenAI API key for it to work. The key is stored locally (e.g. in `localStorage`) so treat this as an educational sandbox only.

## License
Released under the MIT License. See the `LICENSE` file for full text.
