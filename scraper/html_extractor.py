"""
HTML içeriklerini işlemek için genişletilmiş fonksiyonlar
"""
import logging
import re
from typing import Dict, Any, List, Tuple, Optional
from bs4 import BeautifulSoup

from scraper.content_extractor import ContentExtractor
from config.settings import MAIN_CONTENT_SELECTOR, HOSPITAL_INFO_SELECTOR

logger = logging.getLogger(__name__)

class HTMLExtractor(ContentExtractor):
    """HTML sayfalarını işlemek için gelişmiş sınıf"""
    
    def __init__(self, main_content_selector: str = MAIN_CONTENT_SELECTOR, 
                 hospital_info_selector: str = HOSPITAL_INFO_SELECTOR):
        """
        HTMLExtractor sınıfını başlat
        
        Args:
            main_content_selector: Ana içeriği seçmek için CSS seçici
            hospital_info_selector: Hastane bilgisini seçmek için CSS seçici
        """
        super().__init__(main_content_selector, hospital_info_selector)
    
    def extract_content(self, html: str, url: str) -> Dict[str, Any]:
        """
        HTML içeriğinden gelişmiş metin ve yapı çıkarma
        
        Args:
            html: HTML içeriği
            url: Sayfanın URL'si
        
        Returns:
            Dict[str, Any]: Çıkarılan içerik
        """
        # Temel içerik çıkarma
        content = super().extract_content(html, url)
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Ek içerikleri çıkar
            content.update({
                'meta_description': self._extract_meta_description(soup),
                'meta_keywords': self._extract_meta_keywords(soup),
                'headings': self._extract_headings(soup),
                'images': self._extract_images(soup, url),
                'content_type': 'text/html'
            })
            
            # İçeriği temizle ve düzenle
            if content['full_text']:
                content['full_text'] = self._clean_text(content['full_text'])
            
            if content['main_content']:
                content['main_content'] = self._clean_text(content['main_content'])
            
            if content['hospital_info']:
                content['hospital_info'] = self._clean_text(content['hospital_info'])
            
            return content
        
        except Exception as e:
            logger.error(f"Gelişmiş HTML çıkarma hatası ({url}): {str(e)}")
            return content
    
    @staticmethod
    def _extract_meta_description(soup: BeautifulSoup) -> Optional[str]:
        """
        Meta açıklama etiketini çıkar
        
        Args:
            soup: BeautifulSoup nesnesi
        
        Returns:
            Optional[str]: Meta açıklama veya bulunamazsa None
        """
        meta_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_tag and 'content' in meta_tag.attrs:
            return meta_tag['content']
        return None
    
    @staticmethod
    def _extract_meta_keywords(soup: BeautifulSoup) -> Optional[str]:
        """
        Meta anahtar kelimeler etiketini çıkar
        
        Args:
            soup: BeautifulSoup nesnesi
        
        Returns:
            Optional[str]: Meta anahtar kelimeler veya bulunamazsa None
        """
        meta_tag = soup.find('meta', attrs={'name': 'keywords'})
        if meta_tag and 'content' in meta_tag.attrs:
            return meta_tag['content']
        return None
    
    @staticmethod
    def _extract_headings(soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Başlık etiketlerini çıkar
        
        Args:
            soup: BeautifulSoup nesnesi
        
        Returns:
            List[Dict[str, Any]]: Başlık listesi
        """
        headings = []
        for level in range(1, 7):
            for heading in soup.find_all(f'h{level}'):
                headings.append({
                    'level': level,
                    'text': heading.get_text(strip=True)
                })
        return headings
    
    @staticmethod
    def _extract_images(soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """
        Görsel etiketlerini ve meta verilerini çıkar
        
        Args:
            soup: BeautifulSoup nesnesi
            base_url: Baz URL
        
        Returns:
            List[Dict[str, Any]]: Görsel listesi
        """
        from urllib.parse import urljoin
        
        images = []
        for img in soup.find_all('img'):
            # Görsel URL'sini al
            src = img.get('src', '')
            if not src:
                continue
            
            # Tam URL oluştur
            full_url = urljoin(base_url, src)
            
            # Görsel meta verilerini al
            alt_text = img.get('alt', '')
            title = img.get('title', '')
            
            images.append({
                'url': full_url,
                'alt': alt_text,
                'title': title
            })
        
        return images
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Metni temizle ve düzenle
        
        Args:
            text: Temizlenecek metin
        
        Returns:
            str: Temizlenmiş metin
        """
        if not text:
            return ""
        
        # Fazla boşlukları temizle
        text = re.sub(r'\s+', ' ', text)
        
        # Çoklu satır sonlarını temizle
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        
        # Başlangıç ve sondaki boşlukları temizle
        text = text.strip()
        
        return text
    
    def extract_structured_data(self, html: str) -> Dict[str, Any]:
        """
        HTML'deki yapılandırılmış verileri çıkar (JSON-LD, microdata vb.)
        
        Args:
            html: HTML içeriği
        
        Returns:
            Dict[str, Any]: Yapılandırılmış veriler
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            structured_data = {}
            
            # JSON-LD verilerini çıkar
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            if json_ld_scripts:
                import json
                json_ld_data = []
                
                for script in json_ld_scripts:
                    try:
                        json_content = script.string
                        if json_content:
                            data = json.loads(json_content)
                            json_ld_data.append(data)
                    except json.JSONDecodeError:
                        continue
                
                if json_ld_data:
                    structured_data['json_ld'] = json_ld_data
            
            # OpenGraph verilerini çıkar
            og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
            if og_tags:
                og_data = {}
                for tag in og_tags:
                    if 'content' in tag.attrs and 'property' in tag.attrs:
                        property_name = tag['property'][3:]  # 'og:' kısmını kaldır
                        og_data[property_name] = tag['content']
                
                if og_data:
                    structured_data['open_graph'] = og_data
            
            # Twitter card verilerini çıkar
            twitter_tags = soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')})
            if twitter_tags:
                twitter_data = {}
                for tag in twitter_tags:
                    if 'content' in tag.attrs and 'name' in tag.attrs:
                        property_name = tag['name'][8:]  # 'twitter:' kısmını kaldır
                        twitter_data[property_name] = tag['content']
                
                if twitter_data:
                    structured_data['twitter_card'] = twitter_data
            
            return structured_data
            
        except Exception as e:
            logger.error(f"Yapılandırılmış veri çıkarma hatası: {str(e)}")
            return {}