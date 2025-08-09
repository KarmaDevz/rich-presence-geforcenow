import time
import win32gui
import win32process
import psutil
import requests
import re
import json
from pypresence import Presence
from datetime import datetime
from bs4 import BeautifulSoup
import subprocess
import os
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog
from deep_translator import GoogleTranslator
import sys
print(f"🐍 Python version: {sys.version}")
print(f"📂 Current working directory: {os.getcwd()}")
load_dotenv()

TEST_RICH_URL = os.getenv("TEST_RICH_URL")
CLIENT_ID = os.getenv("CLIENT_ID")
STEAM_COOKIE = os.getenv("STEAM_COOKIE")
CONFIG_PATH_FILE = os.getenv("CONFIG_PATH_FILE")
UPDATE_INTERVAL=10

NOMBRES_PROPIOS = {
    "Taal's Horn Keep": "Fortaleza del Cuerno de Taal",
    "Gathering the party for an adventure": "Reuniendo al grupo para una aventura",
    "party": "grupo"
}

def traducir(texto, target='es'):
    for k, v in NOMBRES_PROPIOS.items():
        texto = texto.replace(k, v)
    try:
        return GoogleTranslator(source='auto', target=target).translate(texto)
    except Exception as e:
        print(f"⚠️ Error traduciendo: {e}")
        return texto

def find_geforce_now():
    from pathlib import Path
    possible_paths = [
        Path(os.getenv("LOCALAPPDATA", "")) / "NVIDIA Corporation/GeForceNOW/CEF/GeForceNOW.exe"
    ]
    for path in possible_paths:
        if path.exists():
            return str(path)
    return None

def launch_geforce_now():
    gfn_path = find_geforce_now()
    if gfn_path:
        print("🚀 Iniciando GeForce NOW...")
        subprocess.Popen([gfn_path])
    else:
        print("⚠️ No se encontró GeForce NOW. Inícialo manualmente.")


class SteamScraper:
    def __init__(self, steam_cookie):
        self.session = requests.Session()
        self.session.cookies.set('steamLoginSecure', steam_cookie)



    def get_rich_presence(self):
        try:
            print(f"🌐 Haciendo GET a {TEST_RICH_URL}")
            resp = self.session.get(TEST_RICH_URL, timeout=10)
            print(f"📥 Código de estado: {resp.status_code}")
            if "Sign In" in resp.text or "login" in resp.url.lower():
                print("🔒 Parece que la sesión de Steam ha expirado. Actualiza tu cookie.")
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            bold_tag = soup.find('b', string=re.compile(r'Localized Rich Presence Result', re.IGNORECASE))

            if not bold_tag:
                print("❌ No se encontró <b> con 'Localized Rich Presence Result:'")
                return None

            if bold_tag.next_sibling:
                presence_text = bold_tag.next_sibling.strip()
                if not presence_text or "No rich presence keys set" in presence_text:
                    print("ℹ️ No hay rich presence definido para este usuario.")
                    return None
                print(f"✅ Rich Presence encontrado: {presence_text}")
                return presence_text

            print("❌ No se encontró texto de presence junto al <b>")
            return None

        except Exception as e:
            print(f"⚠️ Error scraping Rich Presence: {e}")
            return None

class AdvancedGeForcePresence:
    def __init__(self):
        self.rpc = Presence(CLIENT_ID)
        self.game_mapping = self.load_game_config()
        self.scraper = SteamScraper(STEAM_COOKIE)
        self.last_game = None
        
        try:
            self.rpc.connect()
            print("✅ Discord RPC conectado correctamente")
        except Exception as e:
            print(f"❌ Error al conectar con Discord: {e}")
            raise

    def load_game_config(self):
        if os.path.exists(CONFIG_PATH_FILE):
            with open(CONFIG_PATH_FILE, 'r', encoding='utf-8') as f:
                config_path = f.read().strip()
        else:
            print("📁 Selecciona tu archivo games_config.json...")
            root = tk.Tk()
            root.withdraw()
            config_path = filedialog.askopenfilename(
                title="Selecciona el archivo games_config.json",
                filetypes=[("JSON Files", "*.json")]
            )
            if not config_path:
                print("❌ No se seleccionó ningún archivo.")
                return {}
            with open(CONFIG_PATH_FILE, 'w', encoding='utf-8') as f:
                f.write(config_path)

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"✅ Configuración cargada desde: {config_path}")
                for game, info in config.items():
                    print(f" - {game}: AppID {info.get('steam_appid', 'N/A')}")
                return config
        except Exception as e:
            print(f"❌ Error leyendo archivo de configuración: {e}")
            return {}

    def get_active_game(self):
        try:
            hwnds = []
            win32gui.EnumWindows(lambda h, p: p.append(h) if win32gui.IsWindowVisible(h) else None, hwnds)
            for hwnd in hwnds:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    exe_name = psutil.Process(pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

                if exe_name.lower() != "geforcenow.exe":
                    continue

                title = win32gui.GetWindowText(hwnd)
                match = re.search(r"(.*?)(?:\s*(?:en|on|via|-)?\s*GeForce\s*NOW|®|™|©|\s*$)", title, re.IGNORECASE)
                if not match:
                    continue

                raw_name = match.group(1).strip()
                clean_name = re.sub(r'[®™©]', '', raw_name).strip()

                for game_name, info in self.game_mapping.items():
                    if clean_name.lower() == game_name.lower() or game_name.lower() in clean_name.lower():
                        return info

                return {'name': raw_name, 'image': 'geforce_default', 'client_id': CLIENT_ID}

            return None
        except Exception as e:
            print(f"⚠️ Error detectando juego: {e}")
            return None

    def update_presence(self, game_info):
        if game_info:
            self.last_game = game_info
        else:
            game_info = self.last_game
        if not game_info:
            self.rpc.clear()
            return

        client_id = game_info.get("client_id", CLIENT_ID)
        if self.rpc.client_id != client_id:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception as e:
                print(f"⚠️ Error cerrando presencia anterior: {e}")
            try:
                self.rpc = Presence(client_id)
                self.rpc.connect()
                print(f"🔁 Cambiado client_id a {client_id}")
            except Exception as e:
                print(f"❌ Error al reconectar con nuevo client_id: {e}")
                return

        status = None
        if game_info.get('steam_appid'):
            scraped = self.scraper.get_rich_presence()
            if scraped:
                status = scraped

        has_custom_client = game_info.get("client_id") and game_info.get("client_id") != CLIENT_ID
        
        #print("📦 game_info recibido:", game_info) 

        if has_custom_client:
            print(f"🔄 Usando juego personalizado: {game_info['client_id']}")
        else:
            print(f"🔄 Usando client_id por defecto para: {game_info['name']}")
        details, state = None, None
        def dividir_status(status):
            posibles = ["|", " - ", ":", "›", ">"]
            for sep in posibles:
                if sep in status:
                    return map(str.strip, status.split(sep, 1))
            return status.strip(), None

        if status:

            details, state = dividir_status(status)
        elif not has_custom_client:
            raw_name = game_info.get("name", "").strip().lower()
            if raw_name in ["geforce now", "jueguitos", ""]:
                details = "Buscando qué jugar"
                game_info["image"] = "lib"  
            else:
                details = f"Jugando a {game_info.get('name')}"




        # Traducción opcional
        details = traducir(details) if details else None
        state = traducir(state) if state else None

        presence_data = {
            "details": details,
            "state": state,
            "large_image": game_info.get('image', 'steam'),
            "large_text": game_info.get('name'),
        }

        if game_info.get("icon_key"):
            presence_data["small_image"] = game_info["icon_key"]

        filtered = {k: v for k, v in presence_data.items() if v}
        try:
            self.rpc.update(**filtered)
        except Exception as e:
            print(f"❌ Error actualizando Presence: {e}")

    def run(self):
        print("\n🟢 Iniciando monitor de presencia...")
        try:
            while True:
                game = self.get_active_game()
                self.update_presence(game)
                time.sleep(UPDATE_INTERVAL)
        except KeyboardInterrupt:
            print("\n🔴 Deteniendo monitor...")
        finally:
            self.rpc.clear()
            self.rpc.close()  
if __name__ == "__main__":
    print("🚀 Iniciando sistema de presencia avanzada con scraping...")
    launch_geforce_now()
    presence = AdvancedGeForcePresence()
    presence.run()
