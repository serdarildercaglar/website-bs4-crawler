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

import re

def clean_text(self, text: str) -> str:
    """
    Metni temizle ancak kelime aralarındaki boşlukları koru
    """
    if not text:
        return ""
    
    # HTML etiketlerini boşluklarla değiştir (silmek yerine)
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Satır sonlarını boşluklara dönüştür ama tamamen kaldırma
    # Bu sayede kelimeler satır sonlarında birleşmeyecek
    text = text.replace('\n', ' ')
    
    # Çoklu boşlukları tek boşluğa indirgeme (isteğe bağlı)
    # text = re.sub(r'\s{2,}', ' ', text)
    
    # Noktalama işaretlerinden sonra boşluk ekleyin
    # Ama zaten boşluk varsa eklemeyin
    text = re.sub(r'([.,!?:;])([^\s])', r'\1 \2', text)
    
    return text


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
            
            # İçeriği temizle ve düzenle
            if main_content:
                main_content = self.clean_text(main_content)
            
            if hospital_info:
                hospital_info = self.clean_text(hospital_info)
            
            # Tüm metni al
            full_text = soup.get_text(separator='\n', strip=True)
            full_text = self.clean_text(full_text)
            
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
                    'text': heading.get_text(strip=False)
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
    def clean_text(text):
        if not text:
            return ""
        
        # HTML etiketlerini kaldır (boşluk bırakarak)
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Özel içerik işaretleyicilerini kaldır
        text = re.sub(r'#\d+ *anahlı dal içerik başlıyor: *\[versiyon *: *\d+\]', ' ', text)
        text = re.sub(r'#+ *\d+ *anahlı dal içerik (başlıyor|bitti) *#+', ' ', text)
        
        # Sayfa yapı bilgilerini kaldır
        text = re.sub(r'SiteAgacDallar:[\d\.]+', ' ', text)
        text = re.sub(r'container|page-content-(header|body|footer)', ' ', text)
        
        # Türkçe unvan kısaltmalarından sonra uygun boşluk bırak
        text = re.sub(r'(Dr|Uzm|Prof|Doç)\.\s*([A-ZÇĞİÖŞÜ])', r'\1. \2', text)
        
        # Büyük harfle başlayan kelimelerden önce boşluk olduğundan emin ol 
        # (ama kısaltmalardan sonra gelenleri etkileme)
        text = re.sub(r'([a-zçğıöşü])([A-ZÇĞİÖŞÜ])', r'\1 \2', text)
        
        # Gereksiz boşlukları temizle (ama tamamen kaldırma)
        text = re.sub(r'\s{2,}', ' ', text)
        
        return text.strip()




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