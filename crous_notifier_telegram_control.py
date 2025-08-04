import time
import threading
import requests
from playwright.sync_api import sync_playwright
import subprocess
from flask import Flask, request

# === CONFIG ===
CROUS_ZONES = [
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=2.0699384_48.82861_2.1683504_48.7792297", "versailles"),
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=2.1618073_48.7986499_2.2292168_48.7691721", "velizy"),
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=1.8948052_48.7856651_1.9553357_48.7567725", "maurepas"),
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=1.9692819_48.7997591_2.0240095_48.7479789", "trappes"),
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=2.1506369_48.8306292_2.2009522_48.8122992", "villedavray"),
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=2.2235812_48.817031_2.2799362_48.7744568", "clamart"),
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=2.1785404_48.835385_2.2327393_48.8091299", "sevres"),
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=2.224122_48.902156_2.4697602_48.8155755", "paris"),
    ("https://trouverunlogement.lescrous.fr/tools/41/search?bounds=1.4462445_49.241431_3.5592208_48.1201456", "ile de france")
]
CHECK_INTERVAL = 150
TELEGRAM_BOT_TOKEN = "7419377967:AAF3v-oUKBhjIaGbmGk7eAi6YErzGkyoLvc"
TELEGRAM_CHAT_ID = "6053608629"

# State variables
pause = False
mute = False
active_zones = [True] * len(CROUS_ZONES)

# Flask app for receiving Telegram webhook commands
app = Flask(__name__)

@app.route(f"/bot{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    global pause, mute, active_zones
    data = request.json
    message = data.get("message", {}).get("text", "").strip().lower()
    chat_id = data.get("message", {}).get("chat", {}).get("id")
    if str(chat_id) != TELEGRAM_CHAT_ID:
        return "ignored", 200

    response = "Commande non reconnue."
    if message == "/pause":
        pause = not pause
        response = "⏸️ Pause activée" if pause else "▶️ Reprise"
    elif message == "/info":
        response = (
            "📖 *Commandes disponibles* :\n"
            "/pause – Met en pause / reprend la recherche 🔄\n"
            "/mute – Active / désactive le son 🔕🔔\n"
            "/status – Affiche l’état actuel du bot 📊\n"
            "/disable <id> – Stoppe une zone (ex : /disable 2) ❌\n"
            "/enable <id> – Relance une zone (ex : /enable 2) ✅\n"
            "/info – Affiche cette aide 📋"
        )
    elif message == "/mute":
        mute = not mute
        response = "🔕 Muet activé" if mute else "🔔 Notifications activées"
    elif message == "/status":
        response = "📊 État des zones :\n"
        for i, (_, label) in enumerate(CROUS_ZONES):
            response += f"{i+1}. {label}: {'✅' if active_zones[i] else '❌'}\n"
        response += f"Pause: {'⏸️' if pause else '▶️'}, Mute: {'🔕' if mute else '🔔'}"
    elif message.startswith("/disable "):
        try:
            idx = int(message.split()[1]) - 1
            active_zones[idx] = False
            response = f"❌ Zone {CROUS_ZONES[idx][1]} désactivée"
        except:
            response = "Erreur lors de la désactivation."
    elif message.startswith("/enable "):
        try:
            idx = int(message.split()[1]) - 1
            active_zones[idx] = True
            response = f"✅ Zone {CROUS_ZONES[idx][1]} activée"
        except:
            response = "Erreur lors de l'activation."

    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                  data={"chat_id": TELEGRAM_CHAT_ID, "text": response})
    return "ok", 200

def send_telegram_message(url, label):
    if not mute:
        message = f"🔔 Logement disponible à {label} ! Vérifie : {url}"
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )

def aucun_logement(html):
    return "Aucun logement trouvé" in html or "Aucune résidence disponible" in html

def main_loop():
    subprocess.run(["playwright", "install", "chromium"], check=True)
    subprocess.run(["playwright", "install-deps"], check=True)
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8000), daemon=True).start()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        while True:
            if pause:
                print("⏸️ En pause...")
                time.sleep(5)
                continue
            for i, (url, label) in enumerate(CROUS_ZONES):
                if not active_zones[i]:
                    continue
                try:
                    page.goto(url, timeout=60000)
                    time.sleep(4)
                    html = page.content()
                    if not aucun_logement(html):
                        print(f"🔔 Logement détecté à {label} !")
                        send_telegram_message(url, label)
                    else:
                        print(f"❌ Aucun logement à {label}")
                except Exception as e:
                    print(f"[!] Erreur pour {label} : {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main_loop()
