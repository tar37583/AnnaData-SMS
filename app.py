import os
from dotenv import load_dotenv
import asyncio
import time
from quart import Quart, request, jsonify
import aiohttp

app = Quart(__name__)


load_dotenv() 
# === Environment Variables ===
DEVICE_IP   = os.getenv("DEVICE_IP")
DEVICE_PORT = os.getenv("DEVICE_PORT")
USERNAME    = os.getenv("APP_USERNAME")
PASSWORD    = os.getenv("PASSWORD")
AI_ENDPOINT = os.getenv("AI_ENDPOINT")

# In-memory cache for processed message IDs (deduplication)
processed_ids = {}
DEDUP_TTL = int(os.getenv("DEDUP_TTL", "600"))  # default 10 minutes


# === Lifecycle Hooks ===
@app.before_serving
async def startup():
    app.config["HTTP"] = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=20)
    )
    print("HTTP session ready")


@app.after_serving
async def shutdown():
    await app.config["HTTP"].close()
    print("Shutdown complete")


# === Deduplication ===
def is_processed(message_id: str) -> bool:
    now = time.time()
    # cleanup expired IDs
    expired = [mid for mid, ts in processed_ids.items() if now - ts > DEDUP_TTL]
    for mid in expired:
        processed_ids.pop(mid, None)
    return message_id in processed_ids


def mark_processed(message_id: str):
    processed_ids[message_id] = time.time()


# === AI Service ===
async def generate_response(message: str) -> str | None:
    http: aiohttp.ClientSession = app.config["HTTP"]
    try:
        async with http.post(
            AI_ENDPOINT,
            json={"query": f"{message}. Reply in the same language. Keep it strictly under 100 words, concise and suitable for SMS format."},
            headers={"accept": "application/json", "Content-Type": "application/json"}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()   
                return data.get("response")
            else:
                print(f"AI API error {resp.status}")
                return None
    except Exception as e:
        print(f"AI request failed: {e}")
        return None


# === SMS Sending ===
async def send_sms(phone_number: str, message: str):
    http: aiohttp.ClientSession = app.config["HTTP"]
    url = f"http://{DEVICE_IP}:{DEVICE_PORT}/message"
    payload = {"phoneNumbers": [phone_number], "textMessage": {"text": message}}
    auth = aiohttp.BasicAuth(USERNAME, PASSWORD)

    try:
        async with http.post(url, json=payload, auth=auth) as resp:
            if resp.status == 200 or resp.status == 202:
                print("SMS sent successfully")
            else:
                print(f"SMS send failed {resp.status}")
    except Exception as e:
        print(f"SMS sending error: {e}")


# === Processing Logic ===
async def process_sms(data: dict):
    payload = data.get("payload", {})
    msg = payload.get("message")
    phone = payload.get("phoneNumber")
    received_at = payload.get("receivedAt")

    print("\nIncoming SMS")
    print(f" From: {phone}")
    print(f" Text: {msg}")
    print(f" At  : {received_at}")
    print("-" * 40)

    reply = await generate_response(msg)
    if reply:
        print("AI Reply:", reply)
        await send_sms(phone, reply)
    else:
        print("No reply generated")


# === Webhook Endpoint ===
@app.post("/incoming-sms")
async def incoming_sms():
    data = await request.get_json(force=True)
    message_id = data.get("payload", {}).get("messageId")
    print("Received SMS with ID:", message_id)

    if not message_id:
        return jsonify({"status": "error", "reason": "missing messageId"}), 400

    if is_processed(message_id):
        print(f"Duplicate SMS (ID: {message_id}) — skipping")
        return jsonify({"status": "duplicate"}), 200

    mark_processed(message_id)
    asyncio.create_task(process_sms(data))
    return jsonify({"status": "ok"}), 200


# === Entry Point ===
# Run with:
# uvicorn sms_server:app --host 0.0.0.0 --port 5000