"""
Loglama sistemi için yardımcı fonksiyonlar
"""
import logging
import os
import time
from logging.handlers import RotatingFileHandler

from config.settings import LOG_LEVEL, LOG_FILE

def setup_logger(name, log_file=LOG_FILE, level=LOG_LEVEL):
    """
    Özelleştirilmiş bir logger oluşturur
    
    Args:
        name: Logger adı
        log_file: Log dosyası yolu
        level: Log seviyesi (INFO, DEBUG, vb.)
    
    Returns:
        Logger: Yapılandırılmış logger nesnesi
    """
    # Log klasörünü oluştur
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Log seviyesini belirle
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level = level_map.get(level.upper(), logging.INFO)
    
    # Logger'ı yapılandır
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Log dosyasına yazmak için handler
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    
    # Konsola yazmak için handler
    console_handler = logging.StreamHandler()
    
    # Format belirle
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Handler'ları ekle
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger


class LoggingTimer:
    """İşlem süresini ölçmek ve loglamak için yardımcı sınıf"""
    
    def __init__(self, logger, operation_name="Operation"):
        """
        LoggingTimer sınıfını başlat
        
        Args:
            logger: Logger nesnesi
            operation_name: Loglarda gösterilecek işlem adı
        """
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        """Context manager başlangıcı"""
        self.start_time = time.time()
        self.logger.debug(f"{self.operation_name} başladı")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager bitişi"""
        duration = time.time() - self.start_time
        if exc_type:
            self.logger.error(f"{self.operation_name} hata ile sonlandı: {exc_val}, Süre: {duration:.2f} saniye")
        else:
            self.logger.debug(f"{self.operation_name} tamamlandı, Süre: {duration:.2f} saniye")