# -*- coding: utf-8 -*-
"""
国际化模块 - 提供多语言支持
"""

import json
import os
import logging
import time
from typing import Dict, Any, Optional
from core.settings import load_settings

class I18n:
    """国际化管理类"""
    
    def __init__(self):
        self.current_language = 'zh_CN'
        self.translations = {}
        self.fallback_language = 'zh_CN'
        
        self._load_translations()
        self._load_current_language()
        
        logging.info(f"国际化模块初始化完成 - 当前语言: {self.current_language}, 可用语言: {list(self.translations.keys())}")
    
    def _load_current_language(self):
        """从设置中加载当前语言"""
        try:
            settings = load_settings()
            
            # 优先使用language_code字段
            language_code = settings.get('language_code', None)
            if language_code:
                self.current_language = language_code
                logging.debug(f"[I18N_LOAD_LANG] 使用language_code: {language_code}")
            else:
                # 如果没有language_code，尝试从language字段转换
                original_language = settings.get('language', 'zh_CN')
                logging.debug(f"[I18N_LOAD_LANG] 设置文件中的语言: {original_language}")
                
                # 显示名称到语言代码的映射
                display_to_code = {
                    '简体中文': 'zh_CN',
                    '繁體中文': 'zh_TW', 
                    'English': 'en_US',
                    '日本語': 'ja_JP'
                }
                
                # 如果是显示名称，转换为语言代码
                if original_language in display_to_code:
                    self.current_language = display_to_code[original_language]
                    logging.debug(f"[I18N_LOAD_LANG] 转换显示名称 '{original_language}' 为语言代码: {self.current_language}")
                else:
                    # 假设已经是语言代码
                    self.current_language = original_language
            
            # 验证语言代码是否有效
            if self.current_language not in self.translations:
                logging.warning(f"语言 '{self.current_language}' 不在可用翻译中，回退到 '{self.fallback_language}'")
                self.current_language = self.fallback_language
                
        except Exception as e:
            logging.error(f"加载当前语言设置失败: {e}")
            self.current_language = self.fallback_language
    
    def _load_translations(self):
        """从JSON文件加载所有翻译"""
        self.translations = {}
        
        # 获取locales目录路径
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        locales_dir = os.path.join(current_dir, 'locales')
        
        logging.debug(f"[I18N_LOAD_TRANS] 当前目录: {current_dir}")
        logging.debug(f"[I18N_LOAD_TRANS] 语言文件目录: {locales_dir}")
        logging.debug(f"[I18N_LOAD_TRANS] 目录是否存在: {os.path.exists(locales_dir)}")
        
        # 支持的语言列表
        supported_languages = ['zh_CN', 'zh_TW', 'en_US', 'ja_JP']
        
        loaded_count = 0
        failed_count = 0
        
        for lang_code in supported_languages:
            lang_file = os.path.join(locales_dir, f'{lang_code}.json')
            
            try:
                if os.path.exists(lang_file):
                    file_size = os.path.getsize(lang_file)
                    logging.debug(f"[I18N_LOAD_TRANS] 文件存在，大小: {file_size} 字节")
                    
                    load_start = time.time()
                    with open(lang_file, 'r', encoding='utf-8') as f:
                        translation_data = json.load(f)
                    
                    self.translations[lang_code] = translation_data
                    loaded_count += 1
                else:
                    logging.warning(f"语言文件不存在: {lang_file}")
                    self.translations[lang_code] = {}
                    failed_count += 1
            except json.JSONDecodeError as e:
                logging.error(f"JSON解析失败 {lang_file}: {e}")
                self.translations[lang_code] = {}
                failed_count += 1
            except Exception as e:
                logging.error(f"加载语言文件失败 {lang_file}: {e}")
                self.translations[lang_code] = {}
                failed_count += 1
        
        # 如果没有加载到任何翻译，使用基本的回退翻译
        if not any(self.translations.values()):
            logging.warning("未能加载任何语言文件，使用基本回退翻译")
            
            self.translations = {
                'zh_CN': {
                    'ok': '确定',
                    'cancel': '取消',
                    'save': '保存',
                    'close': '关闭',
                    'yes': '是',
                    'no': '否',
                },
                'en_US': {
                    'ok': 'OK',
                    'cancel': 'Cancel',
                    'save': 'Save',
                    'close': 'Close',
                    'yes': 'Yes',
                    'no': 'No',
                },
                'zh_TW': {
                    'ok': '確定',
                    'cancel': '取消',
                    'save': '儲存',
                    'close': '關閉',
                    'yes': '是',
                    'no': '否',
                },
                'ja_JP': {
                    'ok': 'OK',
                    'cancel': 'キャンセル',
                    'save': '保存',
                    'close': '閉じる',
                    'yes': 'はい',
                    'no': 'いいえ',
                }
            }
            logging.debug(f"[I18N_LOAD_TRANS] 回退翻译创建完成，包含 {len(self.translations)} 个语言")
        else:
            logging.info(f"[I18N_LOAD_TRANS] 翻译加载成功: {loaded_count}/{len(supported_languages)} 个语言，总计 {sum(len(trans) for trans in self.translations.values())} 个翻译条目")
    
    def set_language(self, language_code: str):
        """设置当前语言"""
        if language_code in self.translations:
            old_language = self.current_language
            
            # 检查是否真的需要切换
            if old_language == language_code:
                return
            
            # 验证目标语言的翻译数据
            target_translations = self.translations[language_code]
            translation_count = len(target_translations)
            
            if translation_count == 0:
                logging.warning(f"目标语言 '{language_code}' 翻译数据为空")
            
            # 执行语言切换
            self.current_language = language_code
            logging.info(f"语言切换成功: {old_language} -> {language_code}")
                
        else:
            logging.error(f"不支持的语言代码: {language_code}，支持的语言: {list(self.translations.keys())}")
    
    def get_text(self, key: str, default: Optional[str] = None) -> str:
        """获取翻译文本"""
        try:
            # 尝试从当前语言获取
            if self.current_language in self.translations:
                current_lang_translations = self.translations[self.current_language]
                text = current_lang_translations.get(key)
                
                if text:
                    return text
            else:
                logging.warning(f"当前语言 '{self.current_language}' 不在翻译数据中")
            
            # 回退到默认语言
            if self.fallback_language in self.translations and self.fallback_language != self.current_language:
                fallback_translations = self.translations[self.fallback_language]
                text = fallback_translations.get(key)
                
                if text:
                    return text
            
            # 如果都没有，返回默认值或键名
            result = default or key
            return result
            
        except Exception as e:
            logging.error(f"获取翻译文本失败 '{key}': {e}")
            return default or key
    
    def get_current_language(self) -> str:
        """获取当前语言代码"""
        return self.current_language
    
    def get_available_languages(self) -> Dict[str, str]:
        """获取可用语言列表"""
        return {
            'zh_CN': '简体中文',
            'zh_TW': '繁體中文',
            'en_US': 'English',
            'ja_JP': '日本語'
        }

# 全局实例
_i18n_instance = None

def get_i18n() -> I18n:
    """获取国际化实例"""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n()
    return _i18n_instance

def t(key: str, default: Optional[str] = None) -> str:
    """快捷翻译函数"""
    return get_i18n().get_text(key, default)

def set_language(language_code: str):
    """设置语言"""
    get_i18n().set_language(language_code)

def get_current_language() -> str:
    """获取当前语言"""
    return get_i18n().get_current_language()

# 导出全局实例
i18n = get_i18n()