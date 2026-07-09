import threading
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Panamera is alive!", 200

@app.route("/ping")
def ping():
    return "pong", 200

def run():
    # Render expects the service to bind to 0.0.0.0 on port 10000 by default
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()
