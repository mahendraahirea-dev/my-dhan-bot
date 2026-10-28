from dhanhq import DhanContext, dhanhq
import os, time
from flask import Flask
import threading

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot Chaloo Aahe! 🚀"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

CLIENT_ID = os.getenv("CLIENT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

try:
    dhan_context = DhanContext(CLIENT_ID, ACCESS_TOKEN)
    dhan = dhanhq(dhan_context)
    print("✅ Dhan Connected!")
except Exception as e:
    print(f"Error: {e}")

threading.Thread(target=run_flask).start()
while True:
    print("Bot Alive... 💓")
    time.sleep(60)
