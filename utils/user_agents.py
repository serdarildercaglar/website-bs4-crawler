"""
User-Agent yönetimi için yardımcı sınıflar ve fonksiyonlar
"""
import random
from typing import List

from config.settings import USER_AGENTS

class UserAgentManager:
    """User-Agent rotasyonu için sınıf"""
    
    def __init__(self, user_agents: List[str] = None):
        """
        UserAgentManager sınıfını başlat
        
        Args:
            user_agents: Kullanılacak User-Agent listesi
        """
        self.user_agents = user_agents or USER_AGENTS
        self.current_index = 0
    
    def get_random(self) -> str:
        """
        Rastgele bir User-Agent döndür
        
        Returns:
            str: Rastgele User-Agent
        """
        return random.choice(self.user_agents)
    
    def get_next(self) -> str:
        """
        Sıradaki User-Agent'ı döndür
        
        Returns:
            str: Sıradaki User-Agent
        """
        agent = self.user_agents[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.user_agents)
        return agent
    
    def get_headers(self, referer: str = None) -> dict:
        """
        HTTP istekleri için header'ları oluştur
        
        Args:
            referer: İsteğin kaynağı (opsiyonel)
        
        Returns:
            dict: HTTP header'ları
        """
        headers = {
            'User-Agent': self.get_next(),
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache'
        }
        
        if referer:
            headers['Referer'] = referer
        
        return headers