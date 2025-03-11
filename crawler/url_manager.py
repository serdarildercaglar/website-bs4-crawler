"""
URL yönetimi, normalleştirme ve doğrulama
"""
import logging
import hashlib
import re
from typing import List, Set, Dict, Any, Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from config.settings import IMPORTANT_URL_PARAMS

logger = logging.getLogger(__name__)

class URLManager:
    """URL işlemleri yönetimi"""
    
    def __init__(self, base_url: str, important_params: Optional[Set[str]] = None):
        """
        URLManager sınıfını başlat
        
        Args:
            base_url: Ana URL
            important_params: Korunacak URL parametreleri kümesi
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.important_params = important_params or IMPORTANT_URL_PARAMS
        self.visited_urls: Set[str] = set()
        self.visited_hashes: Set[str] = set()
        self.excluded_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.ico', '.svg', '.woff', '.woff2', '.ttf', '.eot'}
    
    def normalize_url(self, url: str) -> str:
        """
        URL'yi normalleştir
        
        Args:
            url: Normalleştirilecek URL
        
        Returns:
            str: Normalleştirilmiş URL
        """
        try:
            parsed = urlparse(url)
            
            # Şemayı ve alan adını küçük harfe çevir
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            
            # Standart port numaralarını kaldır
            if (scheme == 'http' and parsed.port == 80) or (scheme == 'https' and parsed.port == 443):
                netloc = netloc.replace(f':{parsed.port}', '')
            
            # Yol dizinlerindeki gereksiz karmaşık kısımları temizle
            path = parsed.path
            while '/./' in path:
                path = path.replace('/./', '/')
            while '/../' in path:
                path = path.replace('/../', '/')
            
            # Sondaki eğik çizgiyi kaldır (kök dizin dışında)
            if path != '/' and path.endswith('/'):
                path = path[:-1]
            
            # Gereksiz URL parametrelerini filtrele
            query_params = parse_qs(parsed.query)
            filtered_params = {k: v for k, v in query_params.items() if k in self.important_params}
            sorted_query = urlencode(sorted(filtered_params.items()), doseq=True)
            
            # Parçaları birleştir
            normalized = urlunparse((scheme, netloc, path, parsed.params, sorted_query, ''))
            return normalized
        
        except Exception as e:
            logger.error(f"URL normalleştirme hatası: {str(e)}")
            return url
    
    def get_url_hash(self, url: str) -> str:
        """
        URL için benzersiz bir hash değeri oluştur
        
        Args:
            url: Hash değeri oluşturulacak URL
        
        Returns:
            str: URL'nin hash değeri
        """
        normalized_url = self.normalize_url(url)
        return hashlib.md5(normalized_url.encode()).hexdigest()
    
    def is_valid_url(self, url: str) -> bool:
        """
        URL'nin geçerli olup olmadığını kontrol et
        
        Args:
            url: Kontrol edilecek URL
        
        Returns:
            bool: URL geçerliyse True, değilse False
        """
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc) and bool(parsed.scheme)
        except:
            return False
    
    def is_internal_url(self, url: str) -> bool:
        """
        URL'nin iç bağlantı olup olmadığını kontrol et
        
        Args:
            url: Kontrol edilecek URL
        
        Returns:
            bool: İç bağlantıysa True, dış bağlantıysa False
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.base_domain
        except:
            return False
        
    def should_crawl(self, url: str) -> bool:
            """
            URL'nin taranması gerekip gerekmediğini kontrol et
            
            Args:
                url: Kontrol edilecek URL
            
            Returns:
                bool: Taranması gerekiyorsa True, gerekmiyorsa False
            """
            # Özel protokolleri kontrol et
            if url.startswith(('mailto:', 'tel:', 'sms:', 'whatsapp:', 'intent:', 'javascript:')):
                return False
                
            # URL'nin geçerli olduğunu kontrol et
            if not self.is_valid_url(url):
                return False
            
            # İç bağlantı olduğunu kontrol et
            if not self.is_internal_url(url):
                return False
            
            # Daha önce ziyaret edildiğini kontrol et
            normalized_url = self.normalize_url(url)
            if normalized_url in self.visited_urls:
                return False
            
            url_hash = self.get_url_hash(url)
            if url_hash in self.visited_hashes:
                return False
            
            # Dosya uzantısını kontrol et
            _, ext = self.get_url_extension(url)
            if ext and ext.lower() in self.excluded_extensions:
                return False
            
            return True
    
    def mark_as_visited(self, url: str) -> None:
        """
        URL'yi ziyaret edilmiş olarak işaretle
        
        Args:
            url: İşaretlenecek URL
        """
        normalized_url = self.normalize_url(url)
        self.visited_urls.add(normalized_url)
        
        url_hash = self.get_url_hash(url)
        self.visited_hashes.add(url_hash)
    
    @staticmethod
    def get_url_extension(url: str) -> tuple:
        """
        URL'nin dosya adını ve uzantısını al
        
        Args:
            url: İşlenecek URL
        
        Returns:
            tuple: (dosya_adı, uzantı) ikilisi
        """
        path = urlparse(url).path
        filename = path.split('/')[-1]
        
        # Nokta ile ayrılmış uzantıyı bul
        match = re.search(r'\.([^./]+)$', filename)
        if match:
            extension = f".{match.group(1)}"
            return filename, extension
        
        return filename, ""
    
    def filter_urls(self, urls: List[str]) -> List[str]:
        """
        URL listesini filtrele
        
        Args:
            urls: Filtrelenecek URL listesi
        
        Returns:
            List[str]: Filtrelenmiş URL listesi
        """
        filtered = []
        
        for url in urls:
            if self.should_crawl(url):
                filtered.append(url)
        
        return filtered