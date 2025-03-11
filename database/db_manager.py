"""
Veritabanı bağlantı ve işlem yönetimi
"""
import json
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
import hashlib
from urllib.parse import urlparse

from sqlalchemy import create_engine, and_, func, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select as future_select
from sqlalchemy.exc import IntegrityError

from database.models import Base, Page, Link, CrawlSession
from config.settings import DATABASE_URL, BATCH_SIZE

logger = logging.getLogger(__name__)

# SQLite URL'lerini async uyumlu hale getir
if DATABASE_URL.startswith('sqlite:///'):
    ASYNC_DATABASE_URL = DATABASE_URL.replace('sqlite:///', 'sqlite+aiosqlite:///')
else:
    ASYNC_DATABASE_URL = DATABASE_URL


class DatabaseManager:
    """Veritabanı işlemlerini yöneten sınıf"""
    
    def __init__(self):
        """DatabaseManager sınıfını başlat"""
        self.engine = create_async_engine(ASYNC_DATABASE_URL)
        self.session_maker = sessionmaker(
            bind=self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
        self.current_session_id = None
        
    async def init_db(self):
        """Veritabanını başlat ve tabloları oluştur"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Veritabanı tabloları oluşturuldu")
    
    async def start_crawl_session(self, base_url: str, config: Dict[str, Any] = None) -> int:
        """Yeni bir tarama oturumu başlat"""
        async with self.session_maker() as session:
            # Önceki yarım kalmış oturumları kontrol et
            stmt = future_select(CrawlSession).where(
                and_(
                    CrawlSession.base_url == base_url,
                    CrawlSession.status.in_(['running', 'paused'])
                )
            )
            result = await session.execute(stmt)
            existing_session = result.scalars().first()
            
            if existing_session:
                # Var olan oturumu devam ettir
                existing_session.status = 'running'
                self.current_session_id = existing_session.id
                await session.commit()
                logger.info(f"Mevcut tarama oturumu devam ettiriliyor: {existing_session.id}")
                return existing_session.id
            
            # Yeni oturum oluştur
            config_json = json.dumps(config) if config else None
            new_session = CrawlSession(
                base_url=base_url,
                status='running',
                config=config_json
            )
            session.add(new_session)
            await session.commit()
            
            self.current_session_id = new_session.id
            logger.info(f"Yeni tarama oturumu başlatıldı: {new_session.id}")
            return new_session.id
    
    async def end_crawl_session(self, session_id: int, status: str = 'completed') -> None:
        """Tarama oturumunu sonlandır"""
        async with self.session_maker() as session:
            stmt = future_select(CrawlSession).where(CrawlSession.id == session_id)
            result = await session.execute(stmt)
            crawl_session = result.scalars().first()
            
            if crawl_session:
                # Tarama oturumunun durumunu ve bitiş zamanını güncelle
                crawl_session.status = status
                crawl_session.end_time = func.now()
                
                # Taranan sayfa sayısını güncelle
                pages_count_stmt = select(func.count()).select_from(Page).where(
                    Page.crawled_at >= crawl_session.start_time
                )
                pages_count = await session.execute(pages_count_stmt)
                crawl_session.pages_crawled = pages_count.scalar()
                
                await session.commit()
                logger.info(f"Tarama oturumu sonlandırıldı: {session_id}, Durum: {status}")
            else:
                logger.warning(f"Sonlandırılacak tarama oturumu bulunamadı: {session_id}")
    
    async def pause_crawl_session(self, session_id: int) -> None:
        """Tarama oturumunu duraklat"""
        async with self.session_maker() as session:
            stmt = future_select(CrawlSession).where(CrawlSession.id == session_id)
            result = await session.execute(stmt)
            crawl_session = result.scalars().first()
            
            if crawl_session:
                crawl_session.status = 'paused'
                await session.commit()
                logger.info(f"Tarama oturumu duraklatıldı: {session_id}")
            else:
                logger.warning(f"Duraklatılacak tarama oturumu bulunamadı: {session_id}")
    
    @staticmethod
    def get_url_hash(url: str) -> str:
        """URL için benzersiz bir hash oluştur"""
        return hashlib.md5(url.encode()).hexdigest()
    
    async def save_page(self, page_data: Dict[str, Any]) -> Optional[int]:
        """Taranan sayfayı veritabanına kaydet"""
        url = page_data.get('url')
        url_hash = self.get_url_hash(url)
        
        async with self.session_maker() as session:
            # Sayfa daha önce kaydedilmiş mi kontrol et
            stmt = future_select(Page).where(Page.url_hash == url_hash)
            result = await session.execute(stmt)
            existing_page = result.scalars().first()
            
            if existing_page:
                # Sayfa zaten var, sadece güncellenebilir
                for key, value in page_data.items():
                    if key != 'url' and key != 'url_hash' and hasattr(existing_page, key):
                        setattr(existing_page, key, value)
                
                existing_page.crawled_at = func.now()
                try:
                    await session.commit()
                    return existing_page.id
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Sayfa güncellenirken hata: {str(e)}")
                    return None
            
            # Yeni sayfa ekle
            new_page = Page(
                url=url,
                url_hash=url_hash,
                title=page_data.get('title'),
                content_type=page_data.get('content_type'),
                full_text=page_data.get('full_text'),
                main_content=page_data.get('main_content'),
                hospital_info=page_data.get('hospital_info'),
                status_code=page_data.get('status_code'),
                depth=page_data.get('depth', 0),
                last_modified=page_data.get('last_modified'),
                error=page_data.get('error')
            )
            
            try:
                session.add(new_page)
                await session.commit()
                return new_page.id
            except IntegrityError:
                await session.rollback()
                logger.warning(f"Sayfa zaten mevcut: {url}")
                # Yeniden sorgula ve ID'yi döndür
                stmt = future_select(Page).where(Page.url_hash == url_hash)
                result = await session.execute(stmt)
                existing_page = result.scalars().first()
                return existing_page.id if existing_page else None
            except Exception as e:
                await session.rollback()
                logger.error(f"Sayfa kaydedilirken hata: {str(e)}")
                return None
    
    async def save_links(self, source_page_id: int, links: List[Dict[str, Any]]) -> None:
        """Bir sayfadan çıkarılan bağlantıları veritabanına kaydet"""
        async with self.session_maker() as session:
            # Toplu işlem için
            try:
                for i in range(0, len(links), BATCH_SIZE):
                    batch = links[i:i+BATCH_SIZE]
                    link_objects = []
                    
                    for link_data in batch:
                        target_url = link_data.get('url')
                        target_url_hash = self.get_url_hash(target_url)
                        
                        # Bağlantı nesnesini oluştur
                        link_obj = Link(
                            source_id=source_page_id,
                            target_url=target_url,
                            target_url_hash=target_url_hash,
                            is_internal=link_data.get('is_internal', True),
                            is_crawled=link_data.get('is_crawled', False)
                        )
                        link_objects.append(link_obj)
                    
                    # Toplu işlemi gerçekleştir
                    if link_objects:
                        session.add_all(link_objects)
                        await session.commit()
                
                logger.info(f"Toplam {len(links)} bağlantı veritabanına kaydedildi")
            except Exception as e:
                await session.rollback()
                logger.error(f"Bağlantılar kaydedilirken hata: {str(e)}")
    
    async def get_uncrawled_links(self, base_url: str, limit: int = 100) -> List[str]:
        """Taranmamış bağlantıları getir"""
        base_domain = urlparse(base_url).netloc
        
        async with self.session_maker() as session:
            # İç bağlantılardan taranmamış olanları seç
            stmt = future_select(Link.target_url).where(
                and_(
                    Link.is_internal == True,
                    Link.is_crawled == False
                )
            ).limit(limit)
            
            result = await session.execute(stmt)
            links = result.scalars().all()
            
            # Sadece base_url ile aynı domain'e ait olanları filtrele
            filtered_links = [
                link for link in links 
                if urlparse(link).netloc == base_domain
            ]
            
            return filtered_links
    
    async def mark_link_as_crawled(self, url: str) -> None:
        """Bir bağlantıyı taranmış olarak işaretle"""
        url_hash = self.get_url_hash(url)
        
        async with self.session_maker() as session:
            stmt = future_select(Link).where(Link.target_url_hash == url_hash)
            result = await session.execute(stmt)
            links = result.scalars().all()
            
            for link in links:
                link.is_crawled = True
            
            await session.commit()
    
    async def url_exists(self, url: str) -> bool:
        """URL veritabanında kayıtlı mı kontrol et"""
        url_hash = self.get_url_hash(url)
        
        async with self.session_maker() as session:
            # Hem sayfalar hem de bağlantılar arasında kontrol et
            page_stmt = future_select(Page).where(Page.url_hash == url_hash)
            page_result = await session.execute(page_stmt)
            page_exists = page_result.scalars().first() is not None
            
            if page_exists:
                return True
            
            link_stmt = future_select(Link).where(Link.target_url_hash == url_hash)
            link_result = await session.execute(link_stmt)
            link_exists = link_result.scalars().first() is not None
            
            return link_exists
    
    async def get_crawl_stats(self, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Tarama istatistiklerini getir"""
        if not session_id and self.current_session_id:
            session_id = self.current_session_id
        
        stats = {
            'total_pages': 0,
            'total_links': 0,
            'crawled_links': 0,
            'session_info': None
        }
        
        async with self.session_maker() as session:
            # Toplam sayfa sayısını hesapla
            pages_count_stmt = select(func.count()).select_from(Page)
            pages_count = await session.execute(pages_count_stmt)
            stats['total_pages'] = pages_count.scalar()
            
            # Toplam ve taranmış bağlantı sayısını hesapla
            links_count_stmt = select(func.count()).select_from(Link)
            links_count = await session.execute(links_count_stmt)
            stats['total_links'] = links_count.scalar()
            
            crawled_links_stmt = select(func.count()).select_from(Link).where(Link.is_crawled == True)
            crawled_links = await session.execute(crawled_links_stmt)
            stats['crawled_links'] = crawled_links.scalar()
            
            # Oturum bilgisini getir
            if session_id:
                stmt = future_select(CrawlSession).where(CrawlSession.id == session_id)
                result = await session.execute(stmt)
                session_info = result.scalars().first()
                
                if session_info:
                    stats['session_info'] = {
                        'id': session_info.id,
                        'base_url': session_info.base_url,
                        'start_time': session_info.start_time.isoformat() if session_info.start_time else None,
                        'end_time': session_info.end_time.isoformat() if session_info.end_time else None,
                        'pages_crawled': session_info.pages_crawled,
                        'status': session_info.status
                    }
            
            return stats
    
    async def close(self):
        """Veritabanı bağlantısını kapat"""
        await self.engine.dispose()