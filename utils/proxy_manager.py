"""
Proxy yönetimi için yardımcı sınıflar ve fonksiyonlar
"""
import asyncio
import logging
import random
from typing import List, Optional, Set, Dict
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientSession

from config.settings import PROXIES, PROXY_ROTATION_LIMIT

logger = logging.getLogger(__name__)

class ProxyManager:
    """Proxy rotasyonu ve yönetimi için sınıf"""
    
    def __init__(self, proxies: List[str] = None, rotation_limit: int = PROXY_ROTATION_LIMIT):
        """
        ProxyManager sınıfını başlat
        
        Args:
            proxies: Kullanılacak proxy listesi ("ip:port:username:password" formatında)
            rotation_limit: Kaç istekte bir proxy değişeceği
        """
        self.proxies = proxies or PROXIES
        self.rotation_limit = rotation_limit
        self.current_index = 0
        self.rotation_count = 0
        self.failed_proxies: Set[str] = set()
        self.working_proxies: Dict[str, int] = {}  # proxy: başarı sayısı
    
    async def check_proxy(self, session: ClientSession, proxy_url: str) -> bool:
        """
        Proxy'nin çalışıp çalışmadığını kontrol et
        
        Args:
            session: aiohttp oturumu
            proxy_url: Kontrol edilecek proxy URL'si
        
        Returns:
            bool: Proxy çalışıyorsa True, aksi halde False
        """
        try:
            async with session.get('http://httpbin.org/ip', proxy=proxy_url, timeout=5) as response:
                if response.status == 200:
                    # Çalışan proxy'lere başarı puanı ekle
                    self.working_proxies[proxy_url] = self.working_proxies.get(proxy_url, 0) + 1
                    return True
        except Exception as e:
            logger.debug(f"Proxy kontrol hatası ({proxy_url}): {str(e)}")
            pass
        return False
    
    async def format_proxy_url(self, proxy_string: str) -> Optional[str]:
        """
        Ham proxy dizesini URL formatına dönüştür
        
        Args:
            proxy_string: "ip:port:username:password" formatında proxy dizesi
        
        Returns:
            Optional[str]: Proxy URL'si veya hata durumunda None
        """
        try:
            parts = proxy_string.split(':')
            if len(parts) == 2:  # Sadece IP:PORT
                ip, port = parts
                return f"http://{ip}:{port}"
            elif len(parts) == 4:  # IP:PORT:USERNAME:PASSWORD
                ip, port, username, password = parts
                return f"http://{username}:{password}@{ip}:{port}"
            else:
                logger.warning(f"Geçersiz proxy formatı: {proxy_string}")
                return None
        except Exception as e:
            logger.error(f"Proxy URL oluşturma hatası: {str(e)}")
            return None
    
    async def get_next_proxy(self, session: ClientSession = None) -> Optional[str]:
        """
        Bir sonraki çalışan proxy'yi döndür
        
        Args:
            session: aiohttp oturumu (opsiyonel)
        
        Returns:
            Optional[str]: Proxy URL'si veya kullanılabilir proxy yoksa None
        """
        if not self.proxies or len(self.failed_proxies) >= len(self.proxies):
            logger.warning("Kullanılabilir proxy bulunamadı")
            return None
        
        # Otomatik rotasyon sınırına ulaşıldı mı?
        self.rotation_count += 1
        if self.rotation_count >= self.rotation_limit:
            self.rotation_count = 0
            self.current_index = (self.current_index + 1) % len(self.proxies)
        
        # Çalıştığı bilinen proxy'leri öncelikle kullan
        if self.working_proxies and random.random() < 0.8:  # %80 ihtimalle çalışan proxy kullan
            working_proxies = sorted(self.working_proxies.items(), key=lambda x: x[1], reverse=True)
            if working_proxies:
                return working_proxies[0][0]
        
        # Başarısız olmayan bir sonraki proxy'yi bul
        attempts = 0
        max_attempts = len(self.proxies)
        
        while attempts < max_attempts:
            proxy_string = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            
            if proxy_string in self.failed_proxies:
                attempts += 1
                continue
            
            proxy_url = await self.format_proxy_url(proxy_string)
            if not proxy_url:
                self.failed_proxies.add(proxy_string)
                attempts += 1
                continue
            
            # İlk kullanımda proxy'yi test et
            if session and proxy_url not in self.working_proxies:
                if await self.check_proxy(session, proxy_url):
                    return proxy_url
                else:
                    self.failed_proxies.add(proxy_string)
                    attempts += 1
                    continue
            
            return proxy_url
        
        return None
    
    def mark_proxy_failed(self, proxy_url: str) -> None:
        """
        Bir proxy'yi başarısız olarak işaretle
        
        Args:
            proxy_url: Başarısız proxy URL'si
        """
        for proxy_string in self.proxies:
            if proxy_url.endswith(proxy_string.split(':')[0]):
                self.failed_proxies.add(proxy_string)
                if proxy_url in self.working_proxies:
                    del self.working_proxies[proxy_url]
                break
    
    def get_proxy_stats(self) -> Dict:
        """
        Proxy kullanım istatistiklerini döndür
        
        Returns:
            Dict: Proxy istatistikleri
        """
        return {
            "total_proxies": len(self.proxies),
            "failed_proxies": len(self.failed_proxies),
            "working_proxies": len(self.working_proxies)
        }