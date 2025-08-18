from dotenv import load_dotenv
import requests
import os

from requests.auth import HTTPBasicAuth

load_dotenv()

# ==== Environment Variables ====
DEVICE_IP   = os.getenv("DEVICE_IP")
DEVICE_PORT = os.getenv("DEVICE_PORT")
USERNAME    = os.getenv("APP_USERNAME")
PASSWORD    = os.getenv("PASSWORD")
NGROK_URL   = os.getenv("NGROK_URL") # Your ngrok HTTPS URL
# =======================

url = f"http://{DEVICE_IP}:{DEVICE_PORT}/webhooks"
print("Webhook URL:", url)
print(f"{NGROK_URL}/incoming-sms")
payload = {
    "url": f"{NGROK_URL}/incoming-sms",
    "event": "sms:received"
}

response = requests.post(
    url,
    json=payload,
    auth=HTTPBasicAuth(USERNAME, PASSWORD)
)

print("Status:", response.status_code)
print("Response:", response.text)
