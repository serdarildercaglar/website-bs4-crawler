#!/usr/bin/env python3
"""
Web Crawler Ana Uygulama
"""
import sys
import os
import asyncio
import argparse
import json
from typing import Dict, Any, Optional
import logging

from database.db_manager import DatabaseManager
from crawler.crawler import WebCrawler
from utils.logger import setup_logger
from config.settings import (
    MAX_CONCURRENT_REQUESTS, MAX_PAGES, MAX_DEPTH, VERIFY_SSL, USE_PROXIES, REQUEST_TIMEOUT
)

# Global logger
logger = setup_logger(__name__)

async def run_crawler(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Crawler'ı çalıştır
    
    Args:
        args: Komut satırı argümanları
    
    Returns:
        Dict[str, Any]: Tarama sonucu
    """
    logger.info(f"Crawler başlatılıyor: {args.url}")
    
    # Veritabanı yöneticisini oluştur
    db_manager = DatabaseManager()
    
    # Crawler'ı oluştur
    crawler = WebCrawler(
        base_url=args.url,
        db_manager=db_manager,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        concurrency=args.concurrency,
        timeout=args.timeout,
        verify_ssl=not args.no_verify_ssl,
        use_proxies=args.use_proxies
    )
    
    try:
        # Taramayı başlat
        await crawler.start()
        
        # İstatistikleri al
        stats = await crawler.get_stats()
        
        # Veritabanı bağlantısını kapat
        await db_manager.close()
        
        return stats
    
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu")
        # Taramayı duraklat
        await crawler.pause()
        
        # İstatistikleri al
        stats = await crawler.get_stats()
        
        # Veritabanı bağlantısını kapat
        await db_manager.close()
        
        return stats
    
    except Exception as e:
        logger.error(f"Hata: {str(e)}")
        # Veritabanı bağlantısını kapat
        await db_manager.close()
        
        return {"error": str(e)}

async def resume_crawler(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Duraklatılmış crawler'ı devam ettir
    
    Args:
        args: Komut satırı argümanları
    
    Returns:
        Dict[str, Any]: Tarama sonucu
    """
    logger.info(f"Crawler devam ettiriliyor: {args.url}")
    
    # Veritabanı yöneticisini oluştur
    db_manager = DatabaseManager()
    
    # Crawler'ı oluştur
    crawler = WebCrawler(
        base_url=args.url,
        db_manager=db_manager,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        concurrency=args.concurrency,
        timeout=args.timeout,
        verify_ssl=not args.no_verify_ssl,
        use_proxies=args.use_proxies
    )
    
    try:
        # Taramayı devam ettir
        await crawler.resume()
        
        # İstatistikleri al
        stats = await crawler.get_stats()
        
        # Veritabanı bağlantısını kapat
        await db_manager.close()
        
        return stats
    
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu")
        # Taramayı duraklat
        await crawler.pause()
        
        # İstatistikleri al
        stats = await crawler.get_stats()
        
        # Veritabanı bağlantısını kapat
        await db_manager.close()
        
        return stats
    
    except Exception as e:
        logger.error(f"Hata: {str(e)}")
        # Veritabanı bağlantısını kapat
        await db_manager.close()
        
        return {"error": str(e)}

def parse_arguments() -> argparse.Namespace:
    """
    Komut satırı argümanlarını ayrıştır
    
    Returns:
        argparse.Namespace: Ayrıştırılmış argümanlar
    """
    parser = argparse.ArgumentParser(description="Web Crawler")
    
    # Alt komutlar
    subparsers = parser.add_subparsers(dest="command", help="Komut")
    
    # 'crawl' komutu
    crawl_parser = subparsers.add_parser("crawl", help="Yeni bir tarama başlat")
    crawl_parser.add_argument("url", help="Taranacak URL")
    crawl_parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="Maksimum sayfa sayısı")
    crawl_parser.add_argument("--max-depth", type=int, default=MAX_DEPTH, help="Maksimum tarama derinliği")
    crawl_parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENT_REQUESTS, help="Eşzamanlı istek sayısı")
    crawl_parser.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT, help="İstek zaman aşımı (saniye)")
    crawl_parser.add_argument("--no-verify-ssl", action="store_true", help="SSL sertifikasını doğrulama")
    crawl_parser.add_argument("--use-proxies", action="store_true", help="Proxy kullan")
    crawl_parser.add_argument("--output", help="Sonuçları dosyaya yaz")
    
    # 'resume' komutu
    resume_parser = subparsers.add_parser("resume", help="Duraklatılmış bir taramayı devam ettir")
    resume_parser.add_argument("url", help="Devam ettirilecek taramanın URL'si")
    resume_parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="Maksimum sayfa sayısı")
    resume_parser.add_argument("--max-depth", type=int, default=MAX_DEPTH, help="Maksimum tarama derinliği")
    resume_parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENT_REQUESTS, help="Eşzamanlı istek sayısı")
    resume_parser.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT, help="İstek zaman aşımı (saniye)")
    resume_parser.add_argument("--no-verify-ssl", action="store_true", help="SSL sertifikasını doğrulama")
    resume_parser.add_argument("--use-proxies", action="store_true", help="Proxy kullan")
    resume_parser.add_argument("--output", help="Sonuçları dosyaya yaz")
    
    # 'stats' komutu
    stats_parser = subparsers.add_parser("stats", help="Tarama istatistiklerini görüntüle")
    stats_parser.add_argument("--output", help="Sonuçları dosyaya yaz")
    
    args = parser.parse_args()
    
    # Komut verilmediyse yardım göster
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    return args

async def main() -> None:
    """Ana uygulama fonksiyonu"""
    # Argümanları ayrıştır
    args = parse_arguments()
    
    # Komutu işle
    result = None
    
    if args.command == "crawl":
        result = await run_crawler(args)
    
    elif args.command == "resume":
        result = await resume_crawler(args)
    
    elif args.command == "stats":
        # Veritabanı yöneticisini oluştur
        db_manager = DatabaseManager()
        # İstatistikleri al
        result = await db_manager.get_crawl_stats()
        # Veritabanı bağlantısını kapat
        await db_manager.close()
    
    # Sonuçları göster
    if result:
        if args.output:
            # JSON formatında dosyaya yaz
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"Sonuçlar dosyaya yazıldı: {args.output}")
        else:
            # Sonuçları ekrana yazdır
            print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    # Windows'ta asyncio event loop politikasını ayarla
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ana fonksiyonu çalıştır
    asyncio.run(main())