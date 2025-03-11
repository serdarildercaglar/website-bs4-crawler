"""
Web Crawler için ayarlar ve yapılandırma parametreleri
"""
import os
from dotenv import load_dotenv

# .env dosyasını yükle (varsa)
load_dotenv()

# Veri tabanı ayarları
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///crawler_data.db")

# Crawler ayarları
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
RATE_LIMIT = float(os.getenv("RATE_LIMIT", "0.01"))  # Saniye başına istek sayısı
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_FACTOR = float(os.getenv("BACKOFF_FACTOR", "0.5"))
VERIFY_SSL = os.getenv("VERIFY_SSL", "True").lower() == "true"

# Proxy ayarları
USE_PROXIES = os.getenv("USE_PROXIES", "False").lower() == "true"
PROXIES = os.getenv("PROXIES", "").split(",") if os.getenv("PROXIES") else []
PROXY_ROTATION_LIMIT = int(os.getenv("PROXY_ROTATION_LIMIT", "50"))

# Crawler davranış ayarları
MAX_PAGES = int(os.getenv("MAX_PAGES", "0")) or None  # 0 ise tüm sayfalar
MAX_DEPTH = int(os.getenv("MAX_DEPTH", "0")) or None  # 0 ise sınırsız derinlik
IMPORTANT_URL_PARAMS = set(os.getenv("IMPORTANT_URL_PARAMS", "id,page,category").split(","))

# Bellek yönetimi
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))  # Veritabanına toplu yazma için

# İçerik seçiciler
MAIN_CONTENT_SELECTOR = "section.pages-content"  # Ana içerik için
HOSPITAL_INFO_SELECTOR = "#header-middle-content"  # Hastane bilgisi için

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "crawler.log")

# User Agent 
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36',
]