"""
Veritabanı modelleri ve ORM tanımlamaları
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import datetime

Base = declarative_base()

class Page(Base):
    """Taranan web sayfalarının bilgilerini saklayan model"""
    __tablename__ = 'pages'
    
    id = Column(Integer, primary_key=True)
    url = Column(String(1024), unique=True, nullable=False)
    url_hash = Column(String(32), unique=True, nullable=False, index=True)
    title = Column(String(512), nullable=True)
    content_type = Column(String(64), nullable=True)
    full_text = Column(Text, nullable=True)
    main_content = Column(Text, nullable=True)
    hospital_info = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    depth = Column(Integer, nullable=False, default=0)
    crawled_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_modified = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    
    # İndexler
    __table_args__ = (
        Index('idx_url_hash', url_hash),
        Index('idx_crawled_at', crawled_at),
    )
    
    def __repr__(self):
        return f"<Page(url='{self.url}', crawled_at='{self.crawled_at}')>"


class Link(Base):
    """Sayfalar arası bağlantıları saklayan model"""
    __tablename__ = 'links'
    
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('pages.id'), nullable=False)
    target_url = Column(String(1024), nullable=False)
    target_url_hash = Column(String(32), nullable=False)
    is_internal = Column(Boolean, default=True)
    is_crawled = Column(Boolean, default=False)
    discovered_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # İndexler
    __table_args__ = (
        Index('idx_target_url_hash', target_url_hash),
        Index('idx_source_target', source_id, target_url_hash),
        Index('idx_not_crawled', is_crawled),
    )
    
    def __repr__(self):
        return f"<Link(source_id={self.source_id}, target_url='{self.target_url}')>"


class CrawlSession(Base):
    """Tarama oturumu bilgilerini saklayan model"""
    __tablename__ = 'crawl_sessions'
    
    id = Column(Integer, primary_key=True)
    base_url = Column(String(1024), nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    pages_crawled = Column(Integer, default=0)
    status = Column(String(32), default='running')  # running, completed, failed, paused
    config = Column(Text, nullable=True)  # JSON olarak ayarlar
    
    def __repr__(self):
        return f"<CrawlSession(id={self.id}, base_url='{self.base_url}', status='{self.status}')>"