from .base import BaseAI, SpamResult
from .openai_client import OpenAIClient
from config import config

def create_ai_client() -> BaseAI:
    """根据配置创建 AI 客户端"""
    model_type = config.get("ai_model", "openai")
    
    if model_type == "openai":
        return OpenAIClient(
            api_key=config.get("openai.api_key"),
            base_url=config.get("openai.base_url"),
            model=config.get("openai.model")
        )
    elif model_type == "qwen":
        return OpenAIClient(
            api_key=config.get("qwen.api_key"),
            base_url=config.get("qwen.base_url"),
            model=config.get("qwen.model")
        )
    elif model_type == "deepseek":
        return OpenAIClient(
            api_key=config.get("deepseek.api_key"),
            base_url=config.get("deepseek.base_url"),
            model=config.get("deepseek.model")
        )
    elif model_type == "kimi":
        return OpenAIClient(
            api_key=config.get("kimi.api_key"),
            base_url=config.get("kimi.base_url"),
            model=config.get("kimi.model")
        )
    else:
        raise ValueError(f"Unknown AI model: {model_type}")

__all__ = ["create_ai_client", "BaseAI", "SpamResult"]
