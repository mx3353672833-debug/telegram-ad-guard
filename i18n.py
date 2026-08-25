"""
国际化模块 (i18n)
支持多语言切换
"""
import os
import yaml
from pathlib import Path
from typing import Optional

class I18n:
    def __init__(self):
        self.locale = 'zh'  # 默认中文
        self.translations = {}
        self.fallback_locale = 'en'
        self._load_all_locales()
    
    def _load_all_locales(self):
        """加载所有语言文件"""
        locales_dir = Path(__file__).parent / 'locales'
        if not locales_dir.exists():
            return
        
        for file in locales_dir.glob('*.yml'):
            locale = file.stem
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    self.translations[locale] = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Failed to load locale {locale}: {e}")
    
    def set_locale(self, locale: str):
        """设置当前语言"""
        if locale in self.translations:
            self.locale = locale
        else:
            print(f"Locale {locale} not found, using {self.locale}")
    
    def get_locale(self) -> str:
        """获取当前语言"""
        return self.locale
    
    def get_available_locales(self) -> list:
        """获取所有可用语言"""
        return list(self.translations.keys())
    
    def t(self, key: str, **kwargs) -> str:
        """
        获取翻译文本
        
        Args:
            key: 翻译键名
            **kwargs: 格式化参数
        
        Returns:
            翻译后的文本
        
        Example:
            i18n.t('admin_only')
            i18n.t('unban_success_detail', name='John', user_id=123)
        """
        # 先从当前语言获取
        text = self.translations.get(self.locale, {}).get(key)
        
        # 如果没有，从 fallback 语言获取
        if text is None:
            text = self.translations.get(self.fallback_locale, {}).get(key)
        
        # 如果还是没有，返回 key 本身
        if text is None:
            return key
        
        # 格式化参数
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                print(f"Missing format key {e} for translation {key}")
        
        return text


# 全局实例
i18n = I18n()

# 便捷函数
def t(key: str, **kwargs) -> str:
    """翻译文本的便捷函数"""
    return i18n.t(key, **kwargs)

def set_locale(locale: str):
    """设置语言的便捷函数"""
    i18n.set_locale(locale)

def get_locale() -> str:
    """获取当前语言"""
    return i18n.get_locale()
