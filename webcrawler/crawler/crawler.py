"""
Ana web crawler sınıfı
"""
import asyncio
import logging
import time
import traceback
from typing import Dict, List, Set, Any, Optional, Tuple
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession, TCPConnector, ClientTimeout
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from config.settings import (
    MAX_CONCURRENT_REQUESTS, REQUEST_TIMEOUT, MAX_RETRIES, 
    BACKOFF_FACTOR, VERIFY_SSL, USE_PROXIES, BATCH_SIZE
)
from crawler.url_manager import URLManager
from crawler.rate_limiter import RateLimiter
from database.db_manager import DatabaseManager
from scraper.html_extractor import HTMLExtractor
from scraper.pdf_extractor import PDFExtractor
from utils.proxy_manager import ProxyManager
from utils.user_agents import UserAgentManager
from utils.logger import LoggingTimer, setup_logger

logger = setup_logger(__name__)

class WebCrawler:
    """Web sayfalarını taramak için ana sınıf"""
    
    def __init__(
        self, 
        base_url: str, 
        db_manager: DatabaseManager,
        max_pages: Optional[int] = None, 
        max_depth: Optional[int] = None,
        concurrency: int = MAX_CONCURRENT_REQUESTS,
        timeout: int = REQUEST_TIMEOUT,
        verify_ssl: bool = VERIFY_SSL,
        use_proxies: bool = USE_PROXIES
    ):
        """
        WebCrawler sınıfını başlat
        
        Args:
            base_url: Tarama başlangıç URL'si
            db_manager: Veritabanı yöneticisi
            max_pages: Maksimum taranacak sayfa sayısı (None: sınırsız)
            max_depth: Maksimum tarama derinliği (None: sınırsız)
            concurrency: Eşzamanlı istek sayısı
            timeout: İstek zaman aşımı (saniye)
            verify_ssl: SSL sertifikası doğrulama
            use_proxies: Proxy kullanımı
        """
        self.base_url = base_url
        self.db_manager = db_manager
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.use_proxies = use_proxies
        
        # Yardımcı sınıfları başlat
        self.url_manager = URLManager(base_url)
        self.rate_limiter = RateLimiter()
        self.proxy_manager = ProxyManager() if use_proxies else None
        self.user_agent_manager = UserAgentManager()
        
        # İçerik çıkarıcıları başlat
        self.html_extractor = HTMLExtractor()
        self.pdf_extractor = PDFExtractor()
        
        # Durum takibi
        self.crawled_count = 0
        self.start_time = None
        self.end_time = None
        self.current_session_id = None
        self.is_running = False
        self.is_paused = False
        
        # İstatistikler
        self.stats = {
            'total_urls': 0,
            'successful': 0,
            'failed': 0,
            'http_errors': {},
            'content_types': {},
            'avg_response_time': 0,
            'total_response_time': 0
        }
        
        # Görev ve kuyruk yönetimi
        self.active_tasks = set()
        self.url_queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(concurrency)
    
    async def start(self) -> None:
        """Crawler'ı başlat"""
        if self.is_running:
            logger.warning("Crawler zaten çalışıyor")
            return
        
        self.is_running = True
        self.is_paused = False
        self.start_time = time.time()
        
        # Veritabanını başlat
        await self.db_manager.init_db()
        
        # Yeni bir tarama oturumu başlat
        config = {
            'base_url': self.base_url,
            'max_pages': self.max_pages,
            'max_depth': self.max_depth,
            'concurrency': self.concurrency,
            'timeout': self.timeout,
            'verify_ssl': self.verify_ssl,
            'use_proxies': self.use_proxies
        }
        self.current_session_id = await self.db_manager.start_crawl_session(self.base_url, config)
        
        # Başlangıç URL'sini kuyruğa ekle
        await self.url_queue.put((self.base_url, 0))  # (url, depth)
        self.stats['total_urls'] += 1
        
        logger.info(f"Crawling başlatıldı: {self.base_url}")
        
        try:
            # HTTP oturumunu oluştur
            conn = TCPConnector(
                limit=self.concurrency,
                ssl=None if not self.verify_ssl else True,
                force_close=True
            )
            timeout = ClientTimeout(total=self.timeout)
            
            async with ClientSession(connector=conn, timeout=timeout) as session:
                # Sitemap'i çek (varsa)
                try:
                    sitemap_urls = await self.fetch_sitemap(session)
                    # Sitemap URL'lerini kuyruğa ekle
                    for url in sitemap_urls:
                        if not self.url_manager.should_crawl(url):
                            continue
                        await self.url_queue.put((url, 0))
                        self.stats['total_urls'] += 1
                except Exception as e:
                    logger.error(f"Sitemap tarama hatası: {str(e)}")
                
                # Çalışan işçi görevleri oluştur
                workers = [self.worker(session, i) for i in range(self.concurrency)]
                await asyncio.gather(*workers)
        
        finally:
            self.is_running = False
            self.end_time = time.time()
            
            # Tarama oturumunu sonlandır
            if self.current_session_id:
                status = 'paused' if self.is_paused else 'completed'
                await self.db_manager.end_crawl_session(self.current_session_id, status)
            
            # İstatistikleri logla
            self.log_stats()
    
    async def worker(self, session: ClientSession, worker_id: int) -> None:
        """
        Tarama işçisi
        
        Args:
            session: HTTP oturumu
            worker_id: İşçi ID'si
        """
        logger.debug(f"İşçi {worker_id} başlatıldı")
        
        while self.is_running and not self.is_paused:
            # Kuyruktan bir sonraki URL'yi al
            try:
                url, depth = await asyncio.wait_for(self.url_queue.get(), timeout=5)
            except asyncio.TimeoutError:
                # Kuyruk boşsa ve tüm işçiler beklemedeyse, taramayı bitir
                if self.url_queue.empty() and all(t.done() for t in self.active_tasks):
                    logger.info("Taranacak URL kalmadı, tarama sonlandırılıyor")
                    self.is_running = False
                    break
                continue
            
            # Derinlik sınırını kontrol et
            if self.max_depth is not None and depth > self.max_depth:
                self.url_queue.task_done()
                continue
            
            # Sayfa sınırını kontrol et
            if self.max_pages is not None and self.crawled_count >= self.max_pages:
                logger.info(f"Maksimum sayfa sınırına ulaşıldı: {self.max_pages}")
                self.url_queue.task_done()
                self.is_running = False
                break
            
            # URL'yi tekrar kontrol et (başka bir işçi işlemiş olabilir)
            if not self.url_manager.should_crawl(url):
                self.url_queue.task_done()
                continue
            
            # Semaforu al (eşzamanlı istek sayısını sınırla)
            async with self.semaphore:
                # Hız sınırlayıcıyı bekle
                await self.rate_limiter.wait(url)
                
                # URL'yi işle
                task = asyncio.create_task(self.process_url(session, url, depth))
                self.active_tasks.add(task)
                task.add_done_callback(self.active_tasks.discard)
                
                try:
                    await task
                except Exception as e:
                    logger.error(f"URL işleme hatası ({url}): {str(e)}\n{traceback.format_exc()}")
                
                self.url_queue.task_done()
        
        logger.debug(f"İşçi {worker_id} sonlandırıldı")
    
    async def process_url(self, session: ClientSession, url: str, depth: int) -> None:
        """
        URL'yi işle
        
        Args:
            session: HTTP oturumu
            url: İşlenecek URL
            depth: Mevcut derinlik
        """
        logger.debug(f"İşleniyor: {url} (Derinlik: {depth})")
        
        # URL'yi ziyaret edilmiş olarak işaretle
        self.url_manager.mark_as_visited(url)
        
        # İçeriği al
        with LoggingTimer(logger, f"URL çekme ({url})"):
            response_data = await self.fetch_url(session, url, depth)
        
        if not response_data:
            self.stats['failed'] += 1
            return
        
        # İçeriği işle
        page_data = response_data.get('content', {})
        links = page_data.get('links', [])
        content_type = response_data.get('content_type', 'unknown')
        status_code = response_data.get('status_code', 0)
        response_time = response_data.get('response_time', 0)
        
        # İstatistikleri güncelle
        self.crawled_count += 1
        self.stats['successful'] += 1
        self.stats['http_errors'][status_code] = self.stats['http_errors'].get(status_code, 0) + 1
        self.stats['content_types'][content_type] = self.stats['content_types'].get(content_type, 0) + 1
        self.stats['total_response_time'] += response_time
        self.stats['avg_response_time'] = self.stats['total_response_time'] / self.stats['successful']
        
        # Adaptif hız sınırlama
        await self.rate_limiter.adaptive_wait(url, response_time, status_code)
        
        # Sayfayı veritabanına kaydet
        page_id = await self.db_manager.save_page(page_data)
        
        if not page_id:
            logger.error(f"Sayfa kaydedilemedi: {url}")
            return
        
        # Bağlantıları işle
        if links:
            # Bağlantıları veritabanına kaydet
            formatted_links = []
            for link in links:
                link_url = link.get('url')
                formatted_links.append({
                    'url': link_url,
                    'is_internal': link.get('is_internal', self.url_manager.is_internal_url(link_url)),
                    'is_crawled': False
                })
            
            await self.db_manager.save_links(page_id, formatted_links)
            
            # İç bağlantıları kuyruğa ekle
            for link in links:
                link_url = link.get('url')
                is_internal = link.get('is_internal', self.url_manager.is_internal_url(link_url))
                
                if is_internal and self.url_manager.should_crawl(link_url):
                    await self.url_queue.put((link_url, depth + 1))
                    self.stats['total_urls'] += 1
    
    async def fetch_url(self, session: ClientSession, url: str, depth: int, retries: int = MAX_RETRIES) -> Optional[Dict[str, Any]]:
        """
        URL'den içerik getir
        
        Args:
            session: HTTP oturumu
            url: İçerik getirilecek URL
            depth: Mevcut derinlik
            retries: Tekrar deneme sayısı
        
        Returns:
            Optional[Dict[str, Any]]: Getirilen içerik veya None
        """
        backoff_factor = BACKOFF_FACTOR
        headers = self.user_agent_manager.get_headers(referer=self.base_url)
        proxy = None
        
        if self.use_proxies and self.proxy_manager:
            proxy = await self.proxy_manager.get_next_proxy(session)
        
        for attempt in range(retries):
            start_time = time.time()
            
            try:
                async with session.get(
                    url, 
                    headers=headers, 
                    proxy=proxy,
                    allow_redirects=True,
                    ssl=None if not self.verify_ssl else True
                ) as response:
                    elapsed = time.time() - start_time
                    
                    # Durum kodunu kontrol et
                    if response.status == 200:
                        # İçerik türünü al
                        content_type = response.headers.get('Content-Type', '').lower()
                        
                        # İçeriği al
                        content_data = await self._extract_content(response, url, content_type)
                        
                        # Sayfa verilerini oluştur
                        page_data = {
                            'url': url,
                            'status_code': response.status,
                            'content_type': content_type,
                            'depth': depth,
                    'response_time': time.time() - start_time,
                    'content': {
                        'url': url,
                        'error': str(e)
                    }
                } depth,
                            'response_time': elapsed,
                            'content': content_data
                        }
                        
                        return page_data
                    
                    elif response.status in {301, 302, 303, 307, 308}:
                        location = response.headers.get('Location')
                        if location:
                            new_url = urljoin(url, location)
                            logger.info(f"Yönlendirme: {url} -> {new_url}")
                            
                            # Yönlendirilen URL'yi işle
                            if self.url_manager.is_internal_url(new_url) and self.url_manager.should_crawl(new_url):
                                await self.url_queue.put((new_url, depth))
                                self.stats['total_urls'] += 1
                        
                        # Tüm denemeler başarısız oldu
        return None
    
    async def _extract_content(self, response, url: str, content_type: str) -> Dict[str, Any]:
        """
        HTTP yanıtından içeriği çıkar
        
        Args:
            response: HTTP yanıtı
            url: İçerik getirilen URL
            content_type: İçerik türü
        
        Returns:
            Dict[str, Any]: Çıkarılan içerik
        """
        try:
            if 'application/pdf' in content_type:
                # PDF işle
                content = await response.read()
                return await self.pdf_extractor.extract_text(content, url)
            
            elif 'text/html' in content_type or 'application/xhtml+xml' in content_type:
                # HTML işle
                html = await response.text()
                return self.html_extractor.extract_content(html, url)
            
            else:
                # Desteklenmeyen içerik türü
                logger.warning(f"Desteklenmeyen içerik türü: {content_type} ({url})")
                return {
                    'url': url,
                    'title': None,
                    'full_text': None,
                    'main_content': None,
                    'hospital_info': None,
                    'links': [],
                    'content_type': content_type
                }
        
        except Exception as e:
            logger.error(f"İçerik çıkarma hatası ({url}): {str(e)}")
            return {
                'url': url,
                'title': None,
                'full_text': None,
                'main_content': None,
                'hospital_info': None,
                'links': [],
                'error': str(e)
            }
                    
                    elif response.status in {403, 429}:
                        logger.warning(f"Erişim engellendi veya hız sınırı aşıldı: {url} (HTTP {response.status})")
                        
                        # Proxy'yi başarısız olarak işaretle
                        if proxy and self.proxy_manager:
                            self.proxy_manager.mark_proxy_failed(proxy)
                            proxy = await self.proxy_manager.get_next_proxy(session)
                        
                        # Daha uzun bir bekleme süresiyle tekrar dene
                        wait_time = backoff_factor * (2 ** attempt) + (attempt + 1)
                        logger.info(f"Tekrar deneniyor: {url} ({attempt + 1}/{retries}, {wait_time} saniye sonra)")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    else:
                        logger.warning(f"HTTP hatası: {url} (HTTP {response.status})")
                        
                        # Ciddi bir hata ise tekrar deneme
                        if response.status >= 500:
                            wait_time = backoff_factor * (2 ** attempt)
                            logger.info(f"Tekrar deneniyor: {url} ({attempt + 1}/{retries}, {wait_time} saniye sonra)")
                            await asyncio.sleep(wait_time)
                            continue
                        
                        return {
                            'url': url,
                            'status_code': response.status,
                            'content_type': 'error',
                            'depth': depth,
                            'response_time': elapsed,
                            'content': {
                                'url': url,
                                'error': f"HTTP {response.status}"
                            }
                        }
            
            except Exception as e:
                # Tüm hataları yakala
                logger.warning(f"Bağlantı hatası: {url} - {str(e)}")
                
                # Proxy'yi başarısız olarak işaretle
                if proxy and self.proxy_manager:
                    self.proxy_manager.mark_proxy_failed(proxy)
                    proxy = await self.proxy_manager.get_next_proxy(session)
                
                # Son deneme değilse tekrar dene
                if attempt < retries - 1:
                    wait_time = backoff_factor * (2 ** attempt)
                    logger.info(f"Tekrar deneniyor: {url} ({attempt + 1}/{retries}, {wait_time} saniye sonra)")
                    await asyncio.sleep(wait_time)
                    continue
                
                return {
                    'url': url,
                    'status_code': 0,
                    'content_type': 'error',
                    'depth':