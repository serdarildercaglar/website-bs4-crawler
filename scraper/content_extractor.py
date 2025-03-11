"""
Web sayfalarından içerik çıkarma işlemleri
"""
import logging
from typing import Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup

from config.settings import MAIN_CONTENT_SELECTOR, HOSPITAL_INFO_SELECTOR

logger = logging.getLogger(__name__)

class ContentExtractor:
    """Web sayfalarından içerik çıkarmak için temel sınıf"""
    
    def __init__(self, main_content_selector: str = MAIN_CONTENT_SELECTOR, 
                 hospital_info_selector: str = HOSPITAL_INFO_SELECTOR):
        """
        ContentExtractor sınıfını başlat
        
        Args:
            main_content_selector: Ana içeriği seçmek için CSS seçici
            hospital_info_selector: Hastane bilgisini seçmek için CSS seçici
        """
        self.main_content_selector = main_content_selector
        self.hospital_info_selector = hospital_info_selector
    
    def extract_content(self, html: str, url: str) -> Dict[str, Any]:
        """
        HTML içeriğinden metinleri çıkar
        
        Args:
            html: HTML içeriği
            url: Sayfanın URL'si
        
        Returns:
            Dict[str, Any]: Çıkarılan içerik
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Script ve stil içeriklerini kaldır
            for script_or_style in soup(['script', 'style', 'noscript', 'iframe']):
                script_or_style.decompose()
            
            # Sayfa başlığını al
            title = None
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
            
            # Ana içeriği ve hastane bilgisini al
            main_content, hospital_info = self._extract_specific_content(soup)
            
            # Tüm metni al
            full_text = soup.get_text(separator='\n', strip=False)
            
            # Bağlantıları çıkar
            links = self._extract_links(soup, url)
            
            return {
                'title': title,
                'full_text': full_text,
                'main_content': main_content,
                'hospital_info': hospital_info,
                'links': links,
                'url': url
            }
        
        except Exception as e:
            logger.error(f"İçerik çıkarma hatası ({url}): {str(e)}")
            return {
                'title': None,
                'full_text': None,
                'main_content': None,
                'hospital_info': None,
                'links': [],
                'url': url,
                'error': str(e)
            }

                
    def _extract_specific_content(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """
        Belirli içerikleri çıkarırken kelimelerin birleşmemesini sağla
        """
        main_content = None
        hospital_info = None
        
        # Ana içeriği çıkar
        if self.main_content_selector:
            main_content_element = soup.select_one(self.main_content_selector)
            if main_content_element:
                # HTML içindeki metin düğümlerini topla ve aralarında boşluk bırak
                texts = []
                for elem in main_content_element.find_all(text=True):
                    if elem.strip():
                        texts.append(elem.strip())
                
                # Metin parçalarını birleştir, ancak boşluk ekleyerek
                main_content = " ".join(texts)
        
        # Hastane bilgisini çıkar
        if self.hospital_info_selector:
            hospital_info_element = soup.select_one(self.hospital_info_selector)
            if hospital_info_element:
                # HTML içindeki metin düğümlerini topla ve aralarında boşluk bırak
                texts = []
                for elem in hospital_info_element.find_all(text=True):
                    if elem.strip():
                        texts.append(elem.strip())
                
                # Metin parçalarını birleştir, ancak boşluk ekleyerek
                hospital_info = " ".join(texts)
        
        return main_content, hospital_info
    
    @staticmethod
    def _extract_links(soup: BeautifulSoup, base_url: str) -> list:
        """
        HTML'den bağlantıları çıkar
        
        Args:
            soup: BeautifulSoup nesnesi
            base_url: Baz URL
        
        Returns:
            list: Bağlantı listesi
        """
        from urllib.parse import urljoin, urlparse
        
        links = []
        
        # Tüm <a> etiketlerini işle
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')#.strip()
            
            # Boş veya javascript bağlantılarını atla
            if not href or href.startswith('javascript:') or href.startswith('#'):
                continue
            
            # Tam URL oluştur
            full_url = urljoin(base_url, href)
            
            # İç veya dış bağlantı mı kontrol et
            is_internal = urlparse(base_url).netloc == urlparse(full_url).netloc
            
            # Bağlantı metnini al
            link_text = a_tag.get_text(strip=False)
            
            links.append({
                'url': full_url,
                'text': link_text,
                'is_internal': is_internal
            })
        
        return links