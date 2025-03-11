"""
İstek hızı sınırlama ve kontrol
"""
import asyncio
import logging
import time
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class RateLimiter:
    """İstek hızını sınırlandırmak için sınıf"""
    
    def __init__(self, rate_limit: float = 0.5, domain_specific_limits: Optional[Dict[str, float]] = None):
        """
        RateLimiter sınıfını başlat
        
        Args:
            rate_limit: Saniye başına maksimum istek sayısı (varsayılan 0.5, yani 2 saniyede 1)
            domain_specific_limits: Alan adlarına özel sınırlar (alan adı: saniye başına istek)
        """
        self.rate_limit = rate_limit
        self.domain_specific_limits = domain_specific_limits or {}
        self.last_request_time: Dict[str, float] = {}
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
    
    async def wait(self, url: str) -> None:
        """
        URL'ye istek yapmadan önce gerekirse bekle
        
        Args:
            url: İstek yapılacak URL
        """
        domain = urlparse(url).netloc
        
        # Alan adına özel semaphore'u al veya oluştur
        if domain not in self.semaphores:
            # Her alan adı için maksimum 1 eşzamanlı istek (isteğe bağlı değiştirilebilir)
            self.semaphores[domain] = asyncio.Semaphore(1)
        
        # Alan adına özel hız sınırını kontrol et
        domain_rate = self.domain_specific_limits.get(domain, self.rate_limit)
        
        # Minimum bekleme süresi (saniye)
        min_wait_time = 1.0 / domain_rate if domain_rate > 0 else 0
        
        async with self.semaphores[domain]:
            # Son istek zamanını kontrol et
            last_time = self.last_request_time.get(domain, 0)
            current_time = time.time()
            
            # Son istekten beri geçen süre
            elapsed = current_time - last_time
            
            # Gerekirse bekle
            if elapsed < min_wait_time:
                wait_time = min_wait_time - elapsed
                logger.debug(f"{domain} için {wait_time:.2f} saniye bekleniyor...")
                await asyncio.sleep(wait_time)
            
            # Son istek zamanını güncelle
            self.last_request_time[domain] = time.time()
    
    def update_domain_limit(self, domain: str, new_limit: float) -> None:
        """
        Alan adına özel hız sınırını güncelle
        
        Args:
            domain: Alan adı
            new_limit: Saniye başına yeni istek limiti
        """
        self.domain_specific_limits[domain] = new_limit
    
    async def adaptive_wait(self, url: str, response_time: float, status_code: int) -> None:
        """
        Yanıt süresine ve durum koduna göre hız sınırını dinamik olarak ayarla
        
        Args:
            url: İstek yapılan URL
            response_time: Yanıt süresi (saniye)
            status_code: HTTP durum kodu
        """
        domain = urlparse(url).netloc
        current_limit = self.domain_specific_limits.get(domain, self.rate_limit)
        
        # 429 (Too Many Requests) durum kodu veya yüksek yanıt süresi durumunda hızı düşür
        if status_code == 429 or response_time > 5.0:
            new_limit = current_limit * 0.5  # Hızı yarıya düşür
            self.update_domain_limit(domain, new_limit)
            logger.warning(f"{domain} için istek limiti düşürüldü: {current_limit:.2f} -> {new_limit:.2f}/sn")
        
        # Hızlı yanıt ve başarılı durumda hızı hafifçe artır
        elif status_code == 200 and response_time < 1.0:
            # Mevcut limitin 1.1 katına kadar artır (maksimum 1/sn)
            new_limit = min(current_limit * 1.1, 1.0)
            if new_limit > current_limit:
                self.update_domain_limit(domain, new_limit)
                logger.debug(f"{domain} için istek limiti artırıldı: {current_limit:.2f} -> {new_limit:.2f}/sn")