from flask import Flask, jsonify
import requests
import threading
import time
from datetime import datetime, timedelta
import random

app = Flask(__name__)

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.last_update = None
        self.update_interval = 600  # 10 dakika (saniye cinsinden)
        self.lock = threading.Lock()
        
        # İlk proxy listesini yükle
        self.update_proxies()
        
        # Arka plan güncelleme thread'ini başlat
        self.start_background_update()
    
    def get_proxy_sources(self):
        """Proxy kaynakları - istediğiniz gibi özelleştirebilirsiniz"""
        return [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://proxylist.geonode.com/api/proxy-list?protocols=http&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
            "https://www.proxy-list.download/api/v1/get?type=http"
        ]
    
    def update_proxies(self):
        """Proxy listesini güncelle"""
        print(f"[{datetime.now()}] Proxy listesi güncelleniyor...")
        
        new_proxies = []
        
        for source in self.get_proxy_sources():
            try:
                response = requests.get(source, timeout=10)
                if response.status_code == 200:
                    # Farklı formatlardaki proxy'leri parse et
                    lines = response.text.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and ':' in line:
                            if '://' in line:
                                # http://ip:port formatı
                                proxy = line.split('://')[1]
                            else:
                                # ip:port formatı
                                proxy = line
                            new_proxies.append(proxy)
            except Exception as e:
                print(f"Kaynak hatası {source}: {e}")
        
        # Benzersiz proxy'leri al
        unique_proxies = list(set(new_proxies))
        
        with self.lock:
            self.proxies = unique_proxies
            self.last_update = datetime.now()
        
        print(f"[{datetime.now()}] {len(self.proxies)} proxy yüklendi")
    
    def start_background_update(self):
        """Arka planda otomatik güncelleme"""
        def update_loop():
            while True:
                time.sleep(self.update_interval)
                self.update_proxies()
        
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
    
    def get_random_proxy(self):
        """Rastgele bir proxy döndür"""
        with self.lock:
            if not self.proxies:
                return None
            return random.choice(self.proxies)
    
    def get_all_proxies(self):
        """Tüm proxy'leri döndür"""
        with self.lock:
            return self.proxies.copy()
    
    def get_status(self):
        """Sistem durumunu döndür"""
        with self.lock:
            next_update = self.last_update + timedelta(seconds=self.update_interval) if self.last_update else None
            return {
                "total_proxies": len(self.proxies),
                "last_update": self.last_update.isoformat() if self.last_update else None,
                "next_update": next_update.isoformat() if next_update else None,
                "update_interval_seconds": self.update_interval
            }

# Proxy manager oluştur
proxy_manager = ProxyManager()

# API Routes
@app.route('/')
def home():
    return jsonify({
        "message": "Proxy API Service",
        "endpoints": {
            "random_proxy": "/api/proxy/random",
            "all_proxies": "/api/proxy/all", 
            "status": "/api/status"
        }
    })

@app.route('/api/proxy/random')
def get_random_proxy():
    """Rastgele bir proxy döndür"""
    proxy = proxy_manager.get_random_proxy()
    if proxy:
        return jsonify({
            "proxy": proxy,
            "type": "http",
            "source": "random"
        })
    else:
        return jsonify({"error": "No proxies available"}), 404

@app.route('/api/proxy/all')
def get_all_proxies():
    """Tüm proxy'leri döndür"""
    proxies = proxy_manager.get_all_proxies()
    return jsonify({
        "proxies": proxies,
        "count": len(proxies),
        "type": "http"
    })

@app.route('/api/status')
def get_status():
    """Sistem durumunu göster"""
    status = proxy_manager.get_status()
    return jsonify(status)

@app.route('/api/proxy/verified')
def get_verified_proxy():
    """Test edilmiş bir proxy döndür (isteğe bağlı)"""
    proxies = proxy_manager.get_all_proxies()
    
    for proxy in random.sample(proxies, min(10, len(proxies))):
        try:
            test_response = requests.get(
                'http://httpbin.org/ip',
                proxies={'http': f'http://{proxy}', 'https': f'http://{proxy}'},
                timeout=5
            )
            if test_response.status_code == 200:
                return jsonify({
                    "proxy": proxy,
                    "type": "http",
                    "verified": True
                })
        except:
            continue
    
    # Eğer doğrulanmış proxy bulunamazsa, rastgele döndür
    return get_random_proxy()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
