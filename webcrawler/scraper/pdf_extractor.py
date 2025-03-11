"""
PDF dosyalarından metin çıkarma işlemleri
"""
import logging
import fitz  # PyMuPDF
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PDFExtractor:
    """PDF'lerden metin çıkarmak için sınıf"""
    
    def __init__(self):
        """PDFExtractor sınıfını başlat"""
        pass
    
    async def extract_text(self, pdf_content: bytes, url: str) -> Dict[str, Any]:
        """
        PDF içeriğinden metni çıkar
        
        Args:
            pdf_content: PDF dosyasının içeriği (bytes)
            url: PDF'nin URL'si
        
        Returns:
            Dict[str, Any]: Çıkarılan içerik
        """
        try:
            with fitz.open(stream=pdf_content, filetype="pdf") as doc:
                # Tüm sayfaları birleştir
                full_text = ""
                metadata = {}
                toc = []
                structure = []
                
                # Meta bilgileri al
                metadata = self._extract_metadata(doc)
                
                # İçindekiler tablosunu al
                toc = doc.get_toc()
                
                # Her sayfanın içeriğini ve yapısını çıkar
                for page_num, page in enumerate(doc):
                    # Sayfa metnini al
                    page_text = page.get_text()
                    full_text += page_text + "\n\n"
                    
                    # Sayfa yapısı hakkında bilgi topla
                    structure.append({
                        'page_number': page_num + 1,
                        'text_length': len(page_text)
                    })
                
                return {
                    'title': metadata.get('title', None),
                    'full_text': full_text,
                    'main_content': full_text,  # PDF'ler için ana içerik tüm metindir
                    'hospital_info': None,  # PDF'lerde hastane bilgisi belirtilmiyor
                    'links': [],  # PDF'lerde bağlantı çıkarmıyoruz
                    'url': url,
                    'metadata': metadata,
                    'toc': toc,
                    'structure': structure,
                    'content_type': 'application/pdf'
                }
        
        except Exception as e:
            logger.error(f"PDF metin çıkarma hatası ({url}): {str(e)}")
            return {
                'title': None,
                'full_text': None,
                'main_content': None,
                'hospital_info': None,
                'links': [],
                'url': url,
                'error': str(e),
                'content_type': 'application/pdf'
            }
    
    @staticmethod
    def _extract_metadata(doc) -> dict:
        """
        PDF belgesinden meta verileri çıkar
        
        Args:
            doc: PyMuPDF belge nesnesi
        
        Returns:
            dict: Meta veriler
        """
        metadata = {
            'title': doc.metadata.get('title', None),
            'author': doc.metadata.get('author', None),
            'subject': doc.metadata.get('subject', None),
            'keywords': doc.metadata.get('keywords', None),
            'creator': doc.metadata.get('creator', None),
            'producer': doc.metadata.get('producer', None),
            'creation_date': doc.metadata.get('creationDate', None),
            'modification_date': doc.metadata.get('modDate', None),
            'page_count': len(doc)
        }
        
        return metadata