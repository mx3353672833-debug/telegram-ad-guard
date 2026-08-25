from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class SpamResult:
    """AI 识别结果"""
    is_spam: bool           # 是否为垃圾信息
    score: int              # 垃圾评分 0-100
    reason: str             # 判断原因
    mock_text: str          # 嘲讽文本

class BaseAI(ABC):
    """AI 模型基类"""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @abstractmethod
    async def check_text(self, user_info: str, message: str) -> SpamResult:
        """检测文本消息"""
        pass

    @abstractmethod
    async def check_image(self, user_info: str, image_base64: str) -> SpamResult:
        """检测图片消息"""
        pass
