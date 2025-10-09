from flask import Flask, jsonify
from flask_cors import CORS  # <-- CORS ekledik
import requests
import threading
import time
from datetime import datetime, timedelta
import random
import os

app = Flask(__name__)
CORS(app)  # <-- Tüm originlere izin verdik

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.last_update = None
        self.update_interval = 600  # 10 dakika
        self.lock = threading.Lock()
        self.update_proxies()
        self.start_background_update()

    def get_proxy_sources(self):
        return [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://proxylist.geonode.com/api/proxy-list?protocols=http&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
            "https://www.proxy-list.download/api/v1/get?type=http"
        ]

    def update_proxies(self):
        print(f"[{datetime.now()}] Proxy listesi güncelleniyor...")
        new_proxies = []
        for source in self.get_proxy_sources():
            try:
                response = requests.get(source, timeout=10)
                if response.status_code == 200:
                    lines = response.text.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and ':' in line:
                            proxy = line.split('://')[1] if '://' in line else line
                            new_proxies.append(proxy)
            except Exception as e:
                print(f"Kaynak hatası {source}: {e}")
        with self.lock:
            self.proxies = list(set(new_proxies))
            self.last_update = datetime.now()
        print(f"[{datetime.now()}] {len(self.proxies)} proxy yüklendi")

    def start_background_update(self):
        def loop():
            while True:
                time.sleep(self.update_interval)
                self.update_proxies()
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def get_random_proxy(self):
        with self.lock:
            return random.choice(self.proxies) if self.proxies else None

    def get_all_proxies(self):
        with self.lock:
            return self.proxies.copy()

    def get_status(self):
        with self.lock:
            next_update = self.last_update + timedelta(seconds=self.update_interval) if self.last_update else None
            return {
                "total_proxies": len(self.proxies),
                "last_update": self.last_update.isoformat() if self.last_update else None,
                "next_update": next_update.isoformat() if next_update else None,
                "update_interval_seconds": self.update_interval
            }

proxy_manager = ProxyManager()

# API Endpoints
@app.route('/')
def home():
    return jsonify({
        "message": "Proxy API Service",
        "endpoints": {
            "random_proxy": "/api/proxy/random",
            "all_proxies": "/api/proxy/all",
            "status": "/api/status",
            "verified_proxy": "/api/proxy/verified"
        }
    })

@app.route('/api/proxy/random')
def random_proxy():
    proxy = proxy_manager.get_random_proxy()
    if proxy:
        return jsonify({"proxy": proxy, "type": "http", "source": "random"})
    return jsonify({"error": "No proxies available"}), 404

@app.route('/api/proxy/all')
def all_proxies():
    proxies = proxy_manager.get_all_proxies()
    return jsonify({"proxies": proxies, "count": len(proxies), "type": "http"})

@app.route('/api/status')
def status():
    return jsonify(proxy_manager.get_status())

@app.route('/api/proxy/verified')
def verified_proxy():
    proxies = proxy_manager.get_all_proxies()
    for proxy in random.sample(proxies, min(10, len(proxies))):
        try:
            r = requests.get('http://httpbin.org/ip', proxies={'http': f'http://{proxy}', 'https': f'http://{proxy}'}, timeout=5)
            if r.status_code == 200:
                return jsonify({"proxy": proxy, "type": "http", "verified": True})
        except:
            continue
    return random_proxy()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
