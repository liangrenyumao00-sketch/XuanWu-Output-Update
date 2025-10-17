# core/email_notifier.py
import smtplib
import ssl
import logging
import os
import time
import mimetypes
import json
import sqlite3
from collections import defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from email.header import Header
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from core.settings import load_settings, save_settings
from core.config import LOG_DIR, SCREENSHOT_DIR
from core.enhanced_logger import get_enhanced_logger

# 使用专用logger，日志将记录到xuanwu_log.html
logger = logging.getLogger('email_notifier')
enhanced_logger = get_enhanced_logger()

class EmailNotifier(QObject):
    """邮件通知器"""
    
    # 信号
    notification_sent = pyqtSignal(bool, str)  # 发送结果, 消息
    
    def __init__(self):
        super().__init__()
        start_time = time.time()
        enhanced_logger.debug_function_call("EmailNotifier.__init__")
        self.settings = load_settings()
        self.db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'performance.db')
        logging.debug(f"邮件通知器初始化完成，数据库路径: {self.db_path}")
        enhanced_logger.debug_performance("邮件通知器初始化完成", start_time)
        
    def get_email_config(self):
        """获取邮件配置"""
        enhanced_logger.debug_function_call("EmailNotifier.get_email_config")
        # 获取email_template配置
        email_template = self.settings.get('email_template', {})
        logging.debug(f"获取邮件配置，模板配置项数量: {len(email_template)}")
        
        return {
            'enabled': self.settings.get('email_notification_enabled', self.settings.get('email_notify_enabled', False)),
            'smtp_server': self.settings.get('smtp_server', self.settings.get('email_smtp_server', 'smtp.qq.com')),
            'smtp_port': self.settings.get('smtp_port', self.settings.get('email_smtp_port', 587)),
            'sender_email': self.settings.get('sender_email', self.settings.get('email_account', '')),
            'sender_password': self.settings.get('sender_password', self.settings.get('email_password', '')),
            'recipient_email': self.settings.get('recipient_email', self.settings.get('email_account', '')),
            'use_tls': self.settings.get('use_tls', self.settings.get('email_use_tls', True)),
            'use_ssl': self.settings.get('use_ssl', self.settings.get('email_use_ssl', False)),
            'timeout': self.settings.get('timeout', self.settings.get('timeout_seconds', 30)),
            'notification_keywords': self.settings.get('notification_keywords', []),
            'notification_cooldown': self.settings.get('notification_cooldown', 300),  # 5分钟冷却
            # 高级功能设置
            'dynamic_theme_enabled': self.settings.get('dynamic_theme_enabled', False),
            'theme_scheme': self.settings.get('theme_scheme', '自动检测'),
            'theme_color': self.settings.get('theme_color', '#007bff'),
            'gradient_intensity': self.settings.get('gradient_intensity', 50),
            'ai_summary_enabled': self.settings.get('ai_summary_enabled', False),
            'summary_length': self.settings.get('summary_length', '中等(100字)'),
            'summary_style': self.settings.get('summary_style', '简洁明了'),
            'highlight_keywords': self.settings.get('highlight_keywords', False),
            'data_visualization_enabled': self.settings.get('data_visualization_enabled', False),
            'chart_type': self.settings.get('chart_type', '柱状图'),
            'data_range': self.settings.get('data_range', '最近30天'),
            'chart_size': self.settings.get('chart_size', '中(500x300)'),
            'show_data_labels': self.settings.get('show_data_labels', False),
            'multilingual_enabled': self.settings.get('multilingual_enabled', False),
            'default_language': self.settings.get('default_language', '中文(简体)'),
            'auto_detect_language': self.settings.get('auto_detect_language', False),
            'translation_service': self.settings.get('translation_service', '内置词典'),
            'interactive_elements_enabled': self.settings.get('interactive_elements_enabled', False),
            'button_style': self.settings.get('button_style', '现代扁平'),
            'quick_reply': self.settings.get('quick_reply', False),
            'action_buttons': self.settings.get('action_buttons', False),
            'feedback_buttons': self.settings.get('feedback_buttons', False),
            'button_color': self.settings.get('button_color', '#28a745'),
            'template_personalization_enabled': self.settings.get('template_personalization_enabled', False),
            # 从email_template中读取模板个性化配置
            'font_family': email_template.get('font_family', '系统默认'),
            'font_size': email_template.get('font_size', 14),
            'content_density': email_template.get('content_density', '正常'),
            'layout_style': email_template.get('layout_style', '现代卡片'),
            'border_radius': email_template.get('border_radius', 8),
            'shadow_enabled': email_template.get('shadow_enabled', True)
        }
    
    def update_email_config(self, config):
        """更新邮件配置"""
        enhanced_logger.debug_function_call("EmailNotifier.update_email_config", {
            "config_keys": list(config.keys()) if config else []
        })
        logging.debug(f"更新邮件配置，配置项数量: {len(config) if config else 0}")
        # 分离基础配置和高级功能配置
        basic_config_keys = {
            'email_notification_enabled', 'smtp_server', 'smtp_port', 'use_tls',
            'sender_email', 'sender_password', 'recipient_email', 
            'notification_cooldown', 'notification_keywords', 'last_notification_time'
        }
        
        # 高级功能配置映射到email_template
        template_config_mapping = {
            'layout_style': 'layout_style',
            'font_family': 'font_family', 
            'font_size': 'font_size',
            'content_density': 'content_density',
            'border_radius': 'border_radius',
            'shadow_enabled': 'shadow_enabled'
        }
        
        # 更新基础配置
        for key, value in config.items():
            if key in basic_config_keys:
                self.settings[key] = value
        
        # 更新高级功能配置到email_template
        if 'email_template' not in self.settings:
            self.settings['email_template'] = {}
            
        # 映射模板个性化配置
        for config_key, template_key in template_config_mapping.items():
            if config_key in config:
                self.settings['email_template'][template_key] = config[config_key]
        
        # 其他高级功能配置直接保存到根级别
        advanced_config_keys = {
            'dynamic_theme_enabled', 'theme_scheme', 'theme_color', 'gradient_intensity',
            'ai_summary_enabled', 'summary_length', 'summary_style', 'highlight_keywords',
            'data_visualization_enabled', 'chart_type', 'data_range', 'chart_size', 'show_data_labels',
            'multilingual_enabled', 'default_language', 'auto_detect_language', 'translation_service',
            'interactive_elements_enabled', 'button_style', 'quick_reply', 'action_buttons', 
            'feedback_buttons', 'button_color', 'template_personalization_enabled'
        }
        
        for key, value in config.items():
            if key in advanced_config_keys:
                self.settings[key] = value
        
        save_settings(self.settings)
        enhanced_logger.debug_performance("邮件配置更新完成")
        logging.debug("邮件配置已保存")
        
    def validate_config(self, config=None):
        """验证邮件配置"""
        enhanced_logger.debug_function_call("EmailNotifier.validate_config")
        if config is None:
            config = self.get_email_config()
            
        required_fields = ['smtp_server', 'sender_email', 'sender_password', 'recipient_email']
        missing_fields = []
        for field in required_fields:
            if not config.get(field):
                missing_fields.append(field)
                
        if missing_fields:
            enhanced_logger.debug_error("邮件配置验证失败", {"missing_fields": missing_fields})
            logging.debug(f"邮件配置验证失败，缺少字段: {missing_fields}")
            return False, f"缺少必要配置: {', '.join(missing_fields)}"
        
        enhanced_logger.debug_performance("邮件配置验证通过")
        logging.debug("邮件配置验证通过")
        return True, "配置验证通过"
    
    def should_send_notification(self, matched_keywords):
        """判断是否应该发送通知"""
        enhanced_logger.debug_function_call("EmailNotifier.should_send_notification", {
            "matched_keywords": matched_keywords
        })
        config = self.get_email_config()
        logging.debug(f"检查是否发送通知，匹配关键词: {matched_keywords}，邮件通知启用: {config.get('enabled', False)}")
        
        if not config['enabled']:
            return False, "邮件通知未启用"
            
        # 检查是否有配置的通知关键词
        notification_keywords = config.get('notification_keywords', [])
        if notification_keywords:
            # 如果配置了特定关键词，只有匹配这些关键词才发送通知
            if not any(kw in matched_keywords for kw in notification_keywords):
                return False, "未匹配到通知关键词"
        
        # 检查冷却时间
        last_notification_time = self.settings.get('last_notification_time', 0)
        current_time = datetime.now().timestamp()
        cooldown = config.get('notification_cooldown', 300)
        
        if current_time - last_notification_time < cooldown:
            remaining = int(cooldown - (current_time - last_notification_time))
            return False, f"通知冷却中，还需等待 {remaining} 秒"
            
        return True, "可以发送通知"
    
    def _get_theme_colors(self, matched_keywords):
        """根据关键词类型获取动态主题色彩"""
        # 定义不同类型关键词的主题色彩
        theme_colors = {
            'urgent': {
                'primary': '#dc3545',
                'secondary': '#f8d7da',
                'gradient': 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)',
                'accent': '#721c24'
            },
            'warning': {
                'primary': '#fd7e14',
                'secondary': '#ffeaa7',
                'gradient': 'linear-gradient(135deg, #fd7e14 0%, #e8590c 100%)',
                'accent': '#8a4a00'
            },
            'info': {
                'primary': '#17a2b8',
                'secondary': '#d1ecf1',
                'gradient': 'linear-gradient(135deg, #17a2b8 0%, #138496 100%)',
                'accent': '#0c5460'
            },
            'success': {
                'primary': '#28a745',
                'secondary': '#d4edda',
                'gradient': 'linear-gradient(135deg, #28a745 0%, #1e7e34 100%)',
                'accent': '#155724'
            },
            'default': {
                'primary': '#667eea',
                'secondary': '#f8f9fa',
                'gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                'accent': '#495057'
            }
        }
        
        # 关键词分类逻辑
        urgent_keywords = ['紧急', '警告', '错误', '异常', '故障', '失败']
        warning_keywords = ['注意', '提醒', '重要', '检查', '确认']
        info_keywords = ['信息', '通知', '更新', '状态', '报告']
        success_keywords = ['成功', '完成', '正常', '通过', '确认']
        
        keyword_text = ' '.join(matched_keywords).lower()
        
        if any(word in keyword_text for word in urgent_keywords):
            return theme_colors['urgent']
        elif any(word in keyword_text for word in warning_keywords):
            return theme_colors['warning']
        elif any(word in keyword_text for word in info_keywords):
            return theme_colors['info']
        elif any(word in keyword_text for word in success_keywords):
            return theme_colors['success']
        else:
            return theme_colors['default']
    
    def _generate_smart_summary(self, ocr_text, matched_keywords, lang='zh'):
        """生成OCR内容的智能摘要"""
        try:
            # 简单的智能摘要算法
            lines = ocr_text.split('\n')
            important_lines = []
            
            # 提取包含关键词的行
            for line in lines:
                if any(keyword in line for keyword in matched_keywords):
                    important_lines.append(line.strip())
            
            # 如果没有包含关键词的行，取前3行
            if not important_lines:
                important_lines = [line.strip() for line in lines[:3] if line.strip()]
            
            # 生成摘要
            if important_lines:
                summary = ' | '.join(important_lines[:3])  # 最多3行
                if len(summary) > 150:
                    summary = summary[:147] + '...'
                return summary
            else:
                return self._get_localized_text('summary_failed', lang)
                
        except Exception as e:
            logger.warning(f"生成智能摘要失败: {e}")
            return self._get_localized_text('summary_generation_failed', lang)
    
    def _get_real_keyword_statistics(self, matched_keywords):
        """获取真实的关键词统计数据"""
        keyword_stats = defaultdict(int)
        
        try:
            # 从日志文件获取关键词统计
            log_dir = LOG_DIR
            if os.path.exists(log_dir):
                for filename in os.listdir(log_dir):
                    if filename.endswith('.txt'):
                        log_path = os.path.join(log_dir, filename)
                        try:
                            with open(log_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                for keyword in matched_keywords:
                                    # 统计关键词在日志中出现的次数
                                    keyword_stats[keyword] += content.count(keyword)
                        except Exception as e:
                            logger.warning(f"读取日志文件失败 {filename}: {e}")
            
            # 从XuanWu_Logs目录获取更多统计数据
            xuanwu_logs_dir = os.path.join(os.path.dirname(__file__), '..', 'XuanWu_Logs')
            if os.path.exists(xuanwu_logs_dir):
                for filename in os.listdir(xuanwu_logs_dir):
                    if filename.endswith('.txt'):
                        log_path = os.path.join(xuanwu_logs_dir, filename)
                        try:
                            with open(log_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                for keyword in matched_keywords:
                                    keyword_stats[keyword] += content.count(keyword)
                        except Exception as e:
                            logger.warning(f"读取XuanWu日志文件失败 {filename}: {e}")
            
            # 如果没有历史数据，使用基础统计
            if not any(keyword_stats.values()):
                for keyword in matched_keywords:
                    keyword_stats[keyword] = 1  # 至少当前匹配了一次
                    
        except Exception as e:
            logging.error(f"获取关键词统计数据失败: {e}")
            # 回退到基础统计
            for keyword in matched_keywords:
                keyword_stats[keyword] = 1
                
        return dict(keyword_stats)
    
    def _generate_statistics_chart(self, matched_keywords, theme, lang='zh'):
        """生成关键词匹配统计图表"""
        try:
            # 获取真实统计数据
            keyword_stats = self._get_real_keyword_statistics(matched_keywords)
            
            # 动态调整图表尺寸和比例
            keyword_count = len(keyword_stats)
            if keyword_count <= 3:
                chart_width = 350
                chart_height = 220
                min_bar_width = 60
            elif keyword_count <= 6:
                chart_width = 450
                chart_height = 240
                min_bar_width = 50
            else:
                chart_width = 600
                chart_height = 260
                min_bar_width = 40
            
            # 计算柱状图参数，确保不重叠
            max_count = max(keyword_stats.values()) if keyword_stats else 1
            # 设置最小比例基准值，避免小数值占满整个图表
            scale_base = max(max_count, 50)  # 至少按50为基准进行缩放
            available_width = chart_width - 40  # 左右边距各20
            bar_spacing = 15  # 柱子间距
            total_spacing = bar_spacing * (keyword_count - 1) if keyword_count > 1 else 0
            bar_width = max(min_bar_width, (available_width - total_spacing) // keyword_count)
            
            # 重新计算实际需要的宽度
            actual_width = keyword_count * bar_width + total_spacing + 40
            if actual_width > chart_width:
                chart_width = actual_width
            
            svg_bars = []
            for i, (keyword, count) in enumerate(keyword_stats.items()):
                # 限制柱子高度，为文本留出更多空间
                max_bar_height = chart_height - 100  # 顶部标题30 + 底部文本40 + 数值文本30
                bar_height = (count / scale_base) * max_bar_height
                x = 20 + i * (bar_width + bar_spacing)
                y = chart_height - bar_height - 60  # 底部留60像素给关键词文本
                
                # 截断过长的关键词
                display_keyword = keyword[:4] + '...' if len(keyword) > 4 else keyword
                
                # 确保数值标签不会与关键词文字重叠
                min_distance_from_bottom = 45  # 至少距离底部关键词文字45像素
                text_y = max(y - 8, 35)  # 至少距离顶部35像素（标题下方）
                
                # 检查是否与底部文字太近
                if (chart_height - text_y) < min_distance_from_bottom:
                    text_y = chart_height - min_distance_from_bottom
                    
                # 如果调整后文字位置在柱子下方，则放在柱子内部
                if text_y > y:
                    text_y = y + 15  # 将文字放在柱子内部
                
                svg_bars.append(f"""
                    <rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" 
                          fill="{theme['primary']}" rx="4" opacity="0.8">
                        <animate attributeName="height" from="0" to="{bar_height}" dur="1s" fill="freeze"/>
                        <animate attributeName="y" from="{chart_height - 50}" to="{y}" dur="1s" fill="freeze"/>
                    </rect>
                    <text x="{x + bar_width//2}" y="{chart_height - 20}" 
                          text-anchor="middle" font-size="10" fill="{theme['accent']}">{display_keyword}</text>
                    <text x="{x + bar_width//2}" y="{text_y}" 
                          text-anchor="middle" font-size="10" fill="{theme['accent']}" font-weight="bold">{count}</text>
                """)
            
            chart_svg = f"""
            <svg width="{chart_width}" height="{chart_height}" viewBox="0 0 {chart_width} {chart_height}" 
                 style="background: white; border-radius: 8px; border: 1px solid {theme['secondary']}; max-width: 100%; height: auto;">
                <defs>
                    <linearGradient id="chartGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" style="stop-color:{theme['primary']};stop-opacity:0.8" />
                        <stop offset="100%" style="stop-color:{theme['primary']};stop-opacity:0.4" />
                    </linearGradient>
                </defs>
                <text x="{chart_width//2}" y="20" text-anchor="middle" font-size="14" 
                       fill="{theme['accent']}" font-weight="bold">{self._get_localized_text('keyword_stats', lang)}</text>
                {''.join(svg_bars)}
            </svg>
            """
            
            return chart_svg
            
        except Exception as e:
            logging.warning(f"生成统计图表失败: {e}")
            return f'<div style="text-align: center; color: #666;">📊 {self._get_localized_text("chart_generation_failed", lang)}</div>'
    
    def _get_language_config(self):
        """获取语言配置"""
        try:
            # 首先检查用户是否启用了多语言支持
            if self.settings.get('multilingual_enabled', False):
                # 如果启用了多语言，使用用户设置的默认语言
                default_language = self.settings.get('default_language', '中文(简体)')
                
                # 将界面语言选项映射到语言代码
                language_mapping = {
                    '中文(简体)': 'zh',
                    'English': 'en',
                    '日本語': 'ja',
                    '한국어': 'ko',
                    'Français': 'fr',
                    'Deutsch': 'de'
                }
                
                return language_mapping.get(default_language, 'zh')
            else:
                # 如果未启用多语言支持，使用系统语言检测
                import locale
                system_lang = locale.getdefaultlocale()[0]
                
                # 根据系统语言确定邮件语言
                if system_lang and system_lang.startswith('en'):
                    return 'en'
                elif system_lang and system_lang.startswith('ja'):
                    return 'ja'
                else:
                    return 'zh'  # 默认中文
        except:
            return 'zh'
    
    def _get_localized_text(self, key, lang='zh', default_value=None):
        """获取本地化文本"""
        texts = {
            'zh': {
                'email_title': 'OCR关键词匹配通知',
                'smart_detection': '智能检测',
                'smart_detection_subtitle': '智能关键词检测系统',
                'smart_summary': '智能摘要',
                'matched_keywords': '匹配关键词',
                'detection_time': '检测时间',
                'detection_success': '检测成功完成',
                'detection_stats': '检测统计',
                'keywords_found': '个关键词匹配',
                'accuracy_rate': '准确率',
                'analysis_report': '分析报告',
                'analysis_report_desc': '详细的检测分析数据',
                'quick_actions': '快速操作',
                'view_details': '查看详情',
                'export_data': '导出数据',
                'mark_processed': '标记已处理',
                'system_signature': '让监控更智能，让工作更高效',
                'ocr_content': 'OCR识别内容',
                'data_analysis': '数据分析',
                'keyword_stats': '关键词匹配统计',
                'trend_7days': '7天匹配趋势',
                'attachment_info': '附件信息',
                'text_log': '文本日志',
                'screenshot': '截图文件',
                'text_log_desc': '包含完整的OCR识别结果和匹配信息',
                'screenshot_desc': '触发关键词匹配的原始截图',
                'auto_sent': '此邮件由OCR关键词监控系统自动发送',
                'send_time': '发送时间',
                'days': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
                'summary_failed': '未能生成内容摘要',
                'summary_generation_failed': '摘要生成失败',
                'chart_generation_failed': '图表生成失败',
                'trend_chart_failed': '趋势图生成失败',
                'test_email_title': '邮件配置测试',
                'test_time': '测试时间',
                'sender_email': '发送邮箱',
                'recipient_email': '接收邮箱',
                'smtp_server': 'SMTP服务器',
                'tls_encryption': 'TLS加密',
                'enabled': '启用',
                'disabled': '禁用',
                'test_success_msg': '如果您收到这封邮件，说明邮件配置测试成功！',
                'auto_sent_test': '此邮件由OCR关键词监控程序自动发送'
            },
            'en': {
                'email_title': 'OCR Keyword Match Notification',
                'smart_detection': 'Smart Detection',
                'smart_summary': 'Smart Summary',
                'matched_keywords': 'Matched Keywords',
                'detection_time': 'Detection Time',
                'ocr_content': 'OCR Recognition Content',
                'data_analysis': 'Data Analysis',
                'keyword_stats': 'Keyword Match Statistics',
                'trend_7days': '7-Day Match Trend',
                'attachment_info': 'Attachment Info',
                'text_log': 'Text Log',
                'screenshot': 'Screenshot',
                'text_log_desc': 'Contains complete OCR recognition results and match information',
                'screenshot_desc': 'Original screenshot that triggered keyword matching',
                'auto_sent': 'This email was sent automatically by OCR keyword monitoring system',
                'send_time': 'Send Time',
                'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                'summary_failed': '无法生成内容摘要',
                'summary_generation_failed': '摘要生成失败',
                'chart_generation_failed': '图表生成失败',
                'trend_chart_failed': '趋势图生成失败',
                'test_email_title': 'Email Configuration Test',
                'test_time': 'Test Time',
                'sender_email': 'Sender Email',
                'recipient_email': 'Recipient Email',
                'smtp_server': 'SMTP Server',
                'tls_encryption': 'TLS Encryption',
                'enabled': 'Enabled',
                'disabled': 'Disabled',
                'test_success_msg': 'If you receive this email, the email configuration test was successful!',
                'auto_sent_test': 'This email was sent automatically by OCR keyword monitoring program'
            },
            'ja': {
                'email_title': 'OCRキーワードマッチ通知',
                'smart_detection': 'スマート検出',
                'smart_summary': 'スマート要約',
                'matched_keywords': 'マッチしたキーワード',
                'detection_time': '検出時間',
                'ocr_content': 'OCR認識内容',
                'data_analysis': 'データ分析',
                'keyword_stats': 'キーワードマッチ統計',
                'trend_7days': '7日間のマッチトレンド',
                'attachment_info': '添付ファイル情報',
                'text_log': 'テキストログ',
                'screenshot': 'スクリーンショット',
                'text_log_desc': '完全なOCR認識結果とマッチ情報を含む',
                'screenshot_desc': 'キーワードマッチをトリガーした元のスクリーンショット',
                'auto_sent': 'このメールはOCRキーワード監視システムによって自動送信されました',
                'send_time': '送信時間',
                'days': ['月', '火', '水', '木', '金', '土', '日'],
                'summary_failed': 'コンテンツ要約を生成できません',
                'summary_generation_failed': '要約生成に失敗しました',
                'chart_generation_failed': 'チャート生成に失敗しました',
                'trend_chart_failed': 'トレンドチャート生成に失敗しました',
                'test_email_title': 'メール設定テスト',
                'test_time': 'テスト時間',
                'sender_email': '送信者メール',
                'recipient_email': '受信者メール',
                'smtp_server': 'SMTPサーバー',
                'tls_encryption': 'TLS暗号化',
                'enabled': '有効',
                'disabled': '無効',
                'test_success_msg': 'このメールを受信した場合、メール設定テストは成功です！',
                'auto_sent_test': 'このメールはOCRキーワード監視プログラムによって自動送信されました'
            },
            'ko': {
                'email_title': 'OCR 키워드 매치 알림',
                'smart_detection': '스마트 감지',
                'smart_summary': '스마트 요약',
                'matched_keywords': '매치된 키워드',
                'detection_time': '감지 시간',
                'ocr_content': 'OCR 인식 내용',
                'data_analysis': '데이터 분석',
                'keyword_stats': '키워드 매치 통계',
                'trend_7days': '7일 매치 트렌드',
                'attachment_info': '첨부파일 정보',
                'text_log': '텍스트 로그',
                'screenshot': '스크린샷',
                'text_log_desc': '완전한 OCR 인식 결과와 매치 정보 포함',
                'screenshot_desc': '키워드 매치를 트리거한 원본 스크린샷',
                'auto_sent': '이 이메일은 OCR 키워드 모니터링 시스템에 의해 자동으로 전송되었습니다',
                'send_time': '전송 시간',
                'days': ['월', '화', '수', '목', '금', '토', '일'],
                'summary_failed': '콘텐츠 요약을 생성할 수 없습니다',
                'summary_generation_failed': '요약 생성에 실패했습니다',
                'chart_generation_failed': '차트 생성에 실패했습니다',
                'trend_chart_failed': '트렌드 차트 생성에 실패했습니다',
                'test_email_title': '이메일 구성 테스트',
                'test_time': '테스트 시간',
                'sender_email': '발신자 이메일',
                'recipient_email': '수신자 이메일',
                'smtp_server': 'SMTP 서버',
                'tls_encryption': 'TLS 암호화',
                'enabled': '활성화',
                'disabled': '비활성화',
                'test_success_msg': '이 이메일을 받으셨다면 이메일 구성 테스트가 성공했습니다!',
                'auto_sent_test': '이 이메일은 OCR 키워드 모니터링 프로그램에 의해 자동으로 전송되었습니다'
            },
            'fr': {
                'email_title': 'Notification de correspondance de mots-clés OCR',
                'smart_detection': 'Détection intelligente',
                'smart_summary': 'Résumé intelligent',
                'matched_keywords': 'Mots-clés correspondants',
                'detection_time': 'Heure de détection',
                'ocr_content': 'Contenu de reconnaissance OCR',
                'data_analysis': 'Analyse des données',
                'keyword_stats': 'Statistiques de correspondance des mots-clés',
                'trend_7days': 'Tendance de correspondance sur 7 jours',
                'attachment_info': 'Informations sur les pièces jointes',
                'text_log': 'Journal texte',
                'screenshot': 'Capture d\'écran',
                'text_log_desc': 'Contient les résultats complets de reconnaissance OCR et les informations de correspondance',
                'screenshot_desc': 'Capture d\'écran originale qui a déclenché la correspondance des mots-clés',
                'auto_sent': 'Cet e-mail a été envoyé automatiquement par le système de surveillance des mots-clés OCR',
                'send_time': 'Heure d\'envoi',
                'days': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
                'summary_failed': 'Impossible de générer un résumé du contenu',
                'summary_generation_failed': 'Échec de la génération du résumé',
                'chart_generation_failed': 'Échec de la génération du graphique',
                'trend_chart_failed': 'Échec de la génération du graphique de tendance',
                'test_email_title': 'Test de configuration email',
                'test_time': 'Heure du test',
                'sender_email': 'Email expéditeur',
                'recipient_email': 'Email destinataire',
                'smtp_server': 'Serveur SMTP',
                'tls_encryption': 'Chiffrement TLS',
                'enabled': 'Activé',
                'disabled': 'Désactivé',
                'test_success_msg': 'Si vous recevez cet email, le test de configuration email a réussi !',
                'auto_sent_test': 'Cet email a été envoyé automatiquement par le programme de surveillance des mots-clés OCR'
            },
            'de': {
                'email_title': 'OCR-Schlüsselwort-Match-Benachrichtigung',
                'smart_detection': 'Intelligente Erkennung',
                'smart_summary': 'Intelligente Zusammenfassung',
                'matched_keywords': 'Übereinstimmende Schlüsselwörter',
                'detection_time': 'Erkennungszeit',
                'ocr_content': 'OCR-Erkennungsinhalt',
                'data_analysis': 'Datenanalyse',
                'keyword_stats': 'Schlüsselwort-Match-Statistiken',
                'trend_7days': '7-Tage-Match-Trend',
                'attachment_info': 'Anhang-Informationen',
                'text_log': 'Textprotokoll',
                'screenshot': 'Screenshot',
                'text_log_desc': 'Enthält vollständige OCR-Erkennungsergebnisse und Match-Informationen',
                'screenshot_desc': 'Original-Screenshot, der das Schlüsselwort-Matching ausgelöst hat',
                'auto_sent': 'Diese E-Mail wurde automatisch vom OCR-Schlüsselwort-Überwachungssystem gesendet',
                'send_time': 'Sendezeit',
                'days': ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'],
                'summary_failed': 'Inhaltszusammenfassung kann nicht generiert werden',
                'summary_generation_failed': 'Zusammenfassungsgenerierung fehlgeschlagen',
                'chart_generation_failed': 'Diagrammgenerierung fehlgeschlagen',
                'trend_chart_failed': 'Trenddiagramm-Generierung fehlgeschlagen',
                'test_email_title': 'E-Mail-Konfigurationstest',
                'test_time': 'Testzeit',
                'sender_email': 'Absender-E-Mail',
                'recipient_email': 'Empfänger-E-Mail',
                'smtp_server': 'SMTP-Server',
                'tls_encryption': 'TLS-Verschlüsselung',
                'enabled': 'Aktiviert',
                'disabled': 'Deaktiviert',
                'test_success_msg': 'Wenn Sie diese E-Mail erhalten, war der E-Mail-Konfigurationstest erfolgreich!',
                'auto_sent_test': 'Diese E-Mail wurde automatisch vom OCR-Schlüsselwort-Überwachungsprogramm gesendet'
            }
        }
        
        result = texts.get(lang, texts['zh']).get(key, default_value or key)
        return result
    
    def _generate_interactive_elements(self, lang='zh', matched_keywords=None):
        """生成增强的交互式元素"""
        try:
            # 本地化文本
            texts = {
                'zh': {
                    'view_details': '查看详情',
                    'mark_resolved': '标记已处理', 
                    'add_whitelist': '添加白名单',
                    'system_settings': '系统设置',
                    'feedback': '反馈问题'
                },
                'en': {
                    'view_details': 'View Details',
                    'mark_resolved': 'Mark as Resolved',
                    'add_whitelist': 'Add to Whitelist', 
                    'system_settings': 'System Settings',
                    'feedback': 'Feedback'
                },
                'ja': {
                    'view_details': '詳細を表示',
                    'mark_resolved': '処理済みとしてマーク',
                    'add_whitelist': 'ホワイトリストに追加',
                    'system_settings': 'システム設定',
                    'feedback': 'フィードバック'
                },
                'ko': {
                    'view_details': '세부사항 보기',
                    'mark_resolved': '처리됨으로 표시',
                    'add_whitelist': '화이트리스트에 추가',
                    'system_settings': '시스템 설정',
                    'feedback': '피드백'
                },
                'fr': {
                    'view_details': 'Voir les détails',
                    'mark_resolved': 'Marquer comme résolu',
                    'add_whitelist': 'Ajouter à la liste blanche',
                    'system_settings': 'Paramètres système',
                    'feedback': 'Commentaires'
                },
                'de': {
                    'view_details': 'Details anzeigen',
                    'mark_resolved': 'Als gelöst markieren',
                    'add_whitelist': 'Zur Whitelist hinzufügen',
                    'system_settings': 'Systemeinstellungen',
                    'feedback': 'Feedback'
                }
            }.get(lang, {
                'view_details': '查看详情',
                'mark_resolved': '标记已处理', 
                'add_whitelist': '添加白名单',
                'system_settings': '系统设置',
                'feedback': '反馈问题'
            })
            
            # 增强的JavaScript功能
            enhanced_js = """
            <script>
            // 增强的通知管理器
            const enhancedNotificationManager = {
                showNotification(message, type = 'success', duration = 3000) {
                    const notification = document.createElement('div');
                    notification.className = `enhanced-notification ${type}`;
                    notification.innerHTML = message;
                    notification.style.cssText = `
                        position: fixed;
                        top: 20px;
                        right: 20px;
                        padding: 15px 20px;
                        border-radius: 8px;
                        color: white;
                        font-weight: 600;
                        z-index: 10000;
                        transform: translateX(400px);
                        transition: transform 0.3s ease;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                        max-width: 350px;
                        word-wrap: break-word;
                    `;
                    
                    // 根据类型设置背景色
                    const backgrounds = {
                        success: 'linear-gradient(135deg, #28a745 0%, #1e7e34 100%)',
                        info: 'linear-gradient(135deg, #17a2b8 0%, #138496 100%)',
                        warning: 'linear-gradient(135deg, #ffc107 0%, #e0a800 100%)',
                        error: 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)'
                    };
                    notification.style.background = backgrounds[type] || backgrounds.success;
                    if(type === 'warning') notification.style.color = '#212529';
                    
                    document.body.appendChild(notification);
                    setTimeout(() => notification.style.transform = 'translateX(0)', 100);
                    
                    setTimeout(() => {
                        notification.style.transform = 'translateX(400px)';
                        setTimeout(() => notification.remove(), 300);
                    }, duration);
                },
                
                showSuccess(message, duration = 3000) {
                    this.showNotification(message, 'success', duration);
                },
                
                showInfo(message, duration = 3000) {
                    this.showNotification(message, 'info', duration);
                },
                
                showWarning(message, duration = 3000) {
                    this.showNotification(message, 'warning', duration);
                },
                
                showError(message, duration = 3000) {
                    this.showNotification(message, 'error', duration);
                }
            };
            
            // 增强的数据管理器
            const enhancedDataManager = {
                // 保存操作日志
                saveOperationLog(action, data) {
                    const logEntry = {
                        timestamp: new Date().toISOString(),
                        action: action,
                        data: data,
                        user_agent: navigator.userAgent,
                        url: window.location.href
                    };
                    
                    let logs = JSON.parse(localStorage.getItem('operationLogs') || '[]');
                    logs.push(logEntry);
                    
                    // 保持最近1000条记录
                    if(logs.length > 1000) {
                        logs = logs.slice(-1000);
                    }
                    
                    localStorage.setItem('operationLogs', JSON.stringify(logs));
                    console.log('📊 操作日志已保存:', logEntry);
                    return logEntry;
                },
                
                // 白名单管理
                addToWhitelist(keywords) {
                    const keywordArray = keywords.split(',').map(k => k.trim()).filter(k => k);
                    let whitelist = JSON.parse(localStorage.getItem('whitelist') || '[]');
                    const newKeywords = keywordArray.filter(k => !whitelist.includes(k));
                    
                    whitelist.push(...newKeywords);
                    localStorage.setItem('whitelist', JSON.stringify(whitelist));
                    
                    this.saveOperationLog('add_whitelist', {
                        keywords: newKeywords,
                        total_count: whitelist.length
                    });
                    
                    return { newKeywords, totalCount: whitelist.length };
                },
                
                // 处理记录管理
                markAsProcessed(ocrText, keywords) {
                    const processedData = {
                        timestamp: new Date().toISOString(),
                        keywords: keywords || [],
                        ocr_preview: ocrText ? ocrText.substring(0, 100) + '...' : '',
                        processor: 'User',
                        status: 'processed',
                        processing_time: new Date().toLocaleString()
                    };
                    
                    let processedRecords = JSON.parse(localStorage.getItem('processedRecords') || '[]');
                    processedRecords.push(processedData);
                    
                    // 保持最近500条记录
                    if(processedRecords.length > 500) {
                        processedRecords = processedRecords.slice(-500);
                    }
                    
                    localStorage.setItem('processedRecords', JSON.stringify(processedRecords));
                    
                    this.saveOperationLog('mark_processed', processedData);
                    return processedData;
                },
                
                // 系统设置管理
                saveSystemSettings(settings) {
                    localStorage.setItem('systemSettings', JSON.stringify(settings));
                    this.saveOperationLog('save_settings', settings);
                    return settings;
                },
                
                getSystemSettings() {
                    const defaultSettings = {
                        sensitivity: 'medium',
                        notificationFrequency: 'realtime',
                        emailNotifications: true,
                        autoWhitelist: false,
                        theme: 'auto',
                        language: 'zh'
                    };
                    
                    const saved = JSON.parse(localStorage.getItem('systemSettings') || '{}');
                    return { ...defaultSettings, ...saved };
                }
            };
            
            // 增强的按钮功能
            function enhancedShowDetails() {
                const ocrContent = document.querySelector('.ocr-content, [class*="ocr"]');
                const content = ocrContent ? ocrContent.textContent : '未找到OCR内容';
                
                const modal = document.createElement('div');
                modal.innerHTML = `
                    <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;justify-content:center;" onclick="this.remove()">
                        <div style="background:white;padding:30px;border-radius:12px;max-width:80%;max-height:80%;overflow:auto;box-shadow:0 10px 30px rgba(0,0,0,0.3);" onclick="event.stopPropagation()">
                            <h3 style="margin:0 0 20px 0;color:#333;display:flex;align-items:center;gap:10px;">📋 OCR识别详情 <span style="font-size:14px;color:#666;font-weight:normal;">${new Date().toLocaleString()}</span></h3>
                            <div style="background:#f8f9fa;padding:20px;border-radius:8px;font-family:monospace;white-space:pre-wrap;max-height:400px;overflow:auto;border:1px solid #dee2e6;">${content}</div>
                            <div style="margin-top:20px;display:flex;gap:10px;justify-content:flex-end;">
                                <button onclick="navigator.clipboard.writeText('${content.replace(/'/g, "\\'")}')"; enhancedNotificationManager.showSuccess('📋 内容已复制到剪贴板')" style="padding:8px 16px;background:#17a2b8;color:white;border:none;border-radius:6px;cursor:pointer;">复制内容</button>
                                <button onclick="this.closest('div').remove()" style="padding:10px 20px;background:#007bff;color:white;border:none;border-radius:6px;cursor:pointer;">关闭</button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal.firstChild);
                
                enhancedDataManager.saveOperationLog('view_details', { content_length: content.length });
                console.log('📋 查看详情功能已触发');
            }
            
            function enhancedMarkAsProcessed() {
                if(confirm('确认将此检测结果标记为已处理？\\n\\n此操作将记录处理时间和相关信息。')) {
                    const ocrContent = document.querySelector('.ocr-content, [class*="ocr"]');
                    const content = ocrContent ? ocrContent.textContent : '';
                    const keywords = window.currentMatchedKeywords || [];
                    
                    const processedData = enhancedDataManager.markAsProcessed(content, keywords);
                    
                    // 更新按钮状态
                    const button = event.target;
                    button.style.background = 'linear-gradient(135deg, #6c757d 0%, #5a6268 100%)';
                    button.innerHTML = '✅ 已处理 (' + new Date().toLocaleTimeString() + ')';
                    button.style.pointerEvents = 'none';
                    
                    enhancedNotificationManager.showSuccess(
                        '✅ 已标记为处理完成<br><small>记录已保存，处理时间: ' + processedData.processing_time + '</small>'
                    );
                    
                    console.log('✅ 标记已处理功能已触发，数据已保存:', processedData);
                }
            }
            
            function enhancedShowWhitelistManager() {
                const currentWhitelist = JSON.parse(localStorage.getItem('whitelist') || '[]');
                const modal = document.createElement('div');
                modal.innerHTML = `
                    <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;justify-content:center;" onclick="this.remove()">
                        <div style="background:white;padding:30px;border-radius:12px;max-width:600px;width:90%;box-shadow:0 10px 30px rgba(0,0,0,0.3);" onclick="event.stopPropagation()">
                            <h3 style="margin:0 0 20px 0;color:#333;display:flex;align-items:center;gap:10px;">🛡️ 白名单管理 <span style="font-size:14px;color:#666;font-weight:normal;">当前: ${currentWhitelist.length} 个关键词</span></h3>
                            
                            <div style="margin-bottom:20px;">
                                <label style="display:block;margin-bottom:8px;font-weight:600;">添加关键词到白名单:</label>
                                <input type="text" id="whitelistInput" placeholder="输入关键词，多个用逗号分隔" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;margin-bottom:10px;">
                                <div style="display:flex;gap:10px;flex-wrap:wrap;">
                                    <button onclick="enhancedAddToWhitelist()" style="padding:8px 16px;background:#ffc107;color:#212529;border:none;border-radius:6px;cursor:pointer;font-weight:600;">添加</button>
                                    <button onclick="enhancedShowCurrentWhitelist()" style="padding:8px 16px;background:#17a2b8;color:white;border:none;border-radius:6px;cursor:pointer;">查看当前</button>
                                    <button onclick="enhancedExportWhitelist()" style="padding:8px 16px;background:#6f42c1;color:white;border:none;border-radius:6px;cursor:pointer;">导出</button>
                                    <button onclick="enhancedClearWhitelist()" style="padding:8px 16px;background:#dc3545;color:white;border:none;border-radius:6px;cursor:pointer;">清空</button>
                                </div>
                            </div>
                            
                            <div id="whitelistStatus" style="background:#f8f9fa;padding:15px;border-radius:6px;margin-bottom:20px;border:1px solid #e9ecef;">
                                <strong>统计信息:</strong><br>
                                <small>当前白名单: <span id="currentCount">${currentWhitelist.length}</span> 个关键词</small><br>
                                <small>最后更新: ${localStorage.getItem('whitelistLastUpdate') || '未知'}</small>
                            </div>
                            
                            <div style="text-align:right;">
                                <button onclick="this.closest('div').remove()" style="padding:10px 20px;background:#6c757d;color:white;border:none;border-radius:6px;cursor:pointer;">关闭</button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal.firstChild);
                
                enhancedDataManager.saveOperationLog('open_whitelist_manager', { current_count: currentWhitelist.length });
                console.log('🛡️ 白名单管理功能已触发');
            }
            
            function enhancedAddToWhitelist() {
                const input = document.getElementById('whitelistInput');
                const keywords = input.value.trim();
                if(keywords) {
                    const result = enhancedDataManager.addToWhitelist(keywords);
                    
                    document.getElementById('currentCount').textContent = result.totalCount;
                    localStorage.setItem('whitelistLastUpdate', new Date().toLocaleString());
                    
                    const message = result.newKeywords.length > 0 ? 
                        `✅ 已添加 ${result.newKeywords.length} 个新关键词<br><small>总计: ${result.totalCount} 个关键词</small>` :
                        `⚠️ 关键词已在白名单中<br><small>当前: ${result.totalCount} 个关键词</small>`;
                    
                    enhancedNotificationManager.showSuccess(message);
                    input.value = '';
                    console.log('🛡️ 白名单已更新:', result);
                }
            }
            
            function enhancedShowCurrentWhitelist() {
                const whitelist = JSON.parse(localStorage.getItem('whitelist') || '[]');
                if(whitelist.length === 0) {
                    enhancedNotificationManager.showInfo('白名单为空');
                    return;
                }
                
                const message = '当前白名单关键词:<br>' + 
                    whitelist.map(k => `<span style="background:#e9ecef;padding:2px 6px;border-radius:3px;margin:2px;display:inline-block;font-size:12px;">${k}</span>`).join('');
                enhancedNotificationManager.showInfo(message, 8000);
            }
            
            function enhancedExportWhitelist() {
                const whitelist = JSON.parse(localStorage.getItem('whitelist') || '[]');
                const exportData = {
                    whitelist: whitelist,
                    export_time: new Date().toISOString(),
                    total_count: whitelist.length,
                    version: '2.1.7'
                };
                
                const dataStr = JSON.stringify(exportData, null, 2);
                const dataBlob = new Blob([dataStr], {type: 'application/json'});
                const url = URL.createObjectURL(dataBlob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `whitelist_export_${new Date().toISOString().split('T')[0]}.json`;
                link.click();
                URL.revokeObjectURL(url);
                
                enhancedNotificationManager.showSuccess('📁 白名单数据已导出');
                enhancedDataManager.saveOperationLog('export_whitelist', { count: whitelist.length });
            }
            
            function enhancedClearWhitelist() {
                if(confirm('确认清空所有白名单关键词？\\n\\n此操作不可撤销！')) {
                    const oldCount = JSON.parse(localStorage.getItem('whitelist') || '[]').length;
                    localStorage.removeItem('whitelist');
                    localStorage.setItem('whitelistLastUpdate', new Date().toLocaleString());
                    
                    document.getElementById('currentCount').textContent = '0';
                    enhancedNotificationManager.showWarning('🗑️ 白名单已清空');
                    enhancedDataManager.saveOperationLog('clear_whitelist', { old_count: oldCount });
                }
            }
            
            function enhancedShowSystemSettings() {
                const settings = enhancedDataManager.getSystemSettings();
                
                const modal = document.createElement('div');
                modal.innerHTML = `
                    <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;justify-content:center;" onclick="this.remove()">
                        <div style="background:white;padding:30px;border-radius:12px;max-width:500px;width:90%;box-shadow:0 10px 30px rgba(0,0,0,0.3);" onclick="event.stopPropagation()">
                            <h3 style="margin:0 0 20px 0;color:#333;display:flex;align-items:center;gap:10px;">⚙️ 系统设置 <span style="font-size:14px;color:#666;font-weight:normal;">v2.1.7</span></h3>
                            
                            <div style="margin-bottom:15px;">
                                <label style="display:block;margin-bottom:5px;font-weight:600;">检测敏感度:</label>
                                <select id="sensitivity" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;">
                                    <option value="low" ${settings.sensitivity === 'low' ? 'selected' : ''}>低 - 仅检测高风险内容</option>
                                    <option value="medium" ${settings.sensitivity === 'medium' ? 'selected' : ''}>中 - 平衡检测</option>
                                    <option value="high" ${settings.sensitivity === 'high' ? 'selected' : ''}>高 - 严格检测</option>
                                </select>
                            </div>
                            
                            <div style="margin-bottom:15px;">
                                <label style="display:block;margin-bottom:5px;font-weight:600;">通知频率:</label>
                                <select id="notificationFrequency" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;">
                                    <option value="realtime" ${settings.notificationFrequency === 'realtime' ? 'selected' : ''}>实时通知</option>
                                    <option value="5min" ${settings.notificationFrequency === '5min' ? 'selected' : ''}>每5分钟汇总</option>
                                    <option value="1hour" ${settings.notificationFrequency === '1hour' ? 'selected' : ''}>每小时汇总</option>
                                    <option value="daily" ${settings.notificationFrequency === 'daily' ? 'selected' : ''}>每日汇总</option>
                                </select>
                            </div>
                            
                            <div style="margin-bottom:15px;">
                                <label style="display:flex;align-items:center;gap:8px;">
                                    <input type="checkbox" id="emailNotifications" ${settings.emailNotifications ? 'checked' : ''}> 启用邮件通知
                                </label>
                            </div>
                            
                            <div style="margin-bottom:15px;">
                                <label style="display:flex;align-items:center;gap:8px;">
                                    <input type="checkbox" id="autoWhitelist" ${settings.autoWhitelist ? 'checked' : ''}> 自动白名单学习
                                </label>
                            </div>
                            
                            <div style="margin-bottom:15px;">
                                <label style="display:block;margin-bottom:5px;font-weight:600;">界面主题:</label>
                                <select id="theme" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;">
                                    <option value="auto" ${settings.theme === 'auto' ? 'selected' : ''}>自动 - 跟随系统</option>
                                    <option value="light" ${settings.theme === 'light' ? 'selected' : ''}>浅色主题</option>
                                    <option value="dark" ${settings.theme === 'dark' ? 'selected' : ''}>深色主题</option>
                                </select>
                            </div>
                            
                            <div style="margin-bottom:20px;">
                                <label style="display:block;margin-bottom:5px;font-weight:600;">界面语言:</label>
                                <select id="language" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;">
                                    <option value="zh" ${settings.language === 'zh' ? 'selected' : ''}>中文</option>
                                    <option value="en" ${settings.language === 'en' ? 'selected' : ''}>English</option>
                                </select>
                            </div>
                            
                            <div style="background:#f8f9fa;padding:15px;border-radius:6px;margin-bottom:20px;border:1px solid #e9ecef;">
                                <small><strong>数据统计:</strong><br>
                                白名单关键词: ${JSON.parse(localStorage.getItem('whitelist') || '[]').length} 个<br>
                                处理记录: ${JSON.parse(localStorage.getItem('processedRecords') || '[]').length} 条<br>
                                操作日志: ${JSON.parse(localStorage.getItem('operationLogs') || '[]').length} 条</small>
                            </div>
                            
                            <div style="text-align:right;display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;">
                                <button onclick="enhancedResetSettings()" style="padding:10px 16px;background:#dc3545;color:white;border:none;border-radius:6px;cursor:pointer;">重置</button>
                                <button onclick="enhancedExportSettings()" style="padding:10px 16px;background:#17a2b8;color:white;border:none;border-radius:6px;cursor:pointer;">导出</button>
                                <button onclick="enhancedSaveSettings()" style="padding:10px 16px;background:#6f42c1;color:white;border:none;border-radius:6px;cursor:pointer;margin-right:10px;">保存</button>
                                <button onclick="this.closest('div').remove()" style="padding:10px 16px;background:#6c757d;color:white;border:none;border-radius:6px;cursor:pointer;">取消</button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal.firstChild);
                
                enhancedDataManager.saveOperationLog('open_system_settings', settings);
                console.log('⚙️ 系统设置功能已触发');
            }
            
            function enhancedSaveSettings() {
                const newSettings = {
                    sensitivity: document.getElementById('sensitivity').value,
                    notificationFrequency: document.getElementById('notificationFrequency').value,
                    emailNotifications: document.getElementById('emailNotifications').checked,
                    autoWhitelist: document.getElementById('autoWhitelist').checked,
                    theme: document.getElementById('theme').value,
                    language: document.getElementById('language').value,
                    lastUpdated: new Date().toISOString()
                };
                
                enhancedDataManager.saveSystemSettings(newSettings);
                enhancedNotificationManager.showSuccess('⚙️ 设置已保存并生效');
                document.querySelector('[style*="position:fixed"]').remove();
                console.log('⚙️ 系统设置已保存:', newSettings);
            }
            
            function enhancedResetSettings() {
                if(confirm('确认重置所有设置到默认值？\\n\\n此操作将清除所有自定义配置！')) {
                    localStorage.removeItem('systemSettings');
                    enhancedNotificationManager.showWarning('⚙️ 设置已重置为默认值');
                    document.querySelector('[style*="position:fixed"]').remove();
                    enhancedDataManager.saveOperationLog('reset_settings', {});
                    console.log('⚙️ 系统设置已重置');
                }
            }
            
            function enhancedExportSettings() {
                const settings = enhancedDataManager.getSystemSettings();
                const exportData = {
                    settings: settings,
                    export_time: new Date().toISOString(),
                    version: '2.1.7',
                    whitelist_count: JSON.parse(localStorage.getItem('whitelist') || '[]').length,
                    processed_count: JSON.parse(localStorage.getItem('processedRecords') || '[]').length
                };
                
                const dataStr = JSON.stringify(exportData, null, 2);
                const dataBlob = new Blob([dataStr], {type: 'application/json'});
                const url = URL.createObjectURL(dataBlob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `system_settings_export_${new Date().toISOString().split('T')[0]}.json`;
                link.click();
                URL.revokeObjectURL(url);
                
                enhancedNotificationManager.showSuccess('📁 设置已导出');
                enhancedDataManager.saveOperationLog('export_settings', settings);
            }
            
            function openFeedbackPage() {
                try {
                    // 获取系统信息
                    const systemInfo = `操作系统: ${navigator.platform}\nPython版本: 3.10.10\n软件版本: XuanWu OCR 2.1.7`;
                    
                    // 反馈模板内容
                    const feedbackBody = `问题描述：\n请详细描述您遇到的问题\n\n\n重现步骤：\n1. \n2. \n3. \n\n系统信息：\n${systemInfo}\n\n联系方式：\n\n\n技术支持：1337555682@qq.com`;
                    
                    const subject = "OCR系统反馈";
                    
                    // 生成mailto链接
                    const mailtoUrl = `mailto:1337555682@qq.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(feedbackBody)}`;
                    
                    // 生成QQ邮箱网页版链接
                    const qqWebUrl = `https://mail.qq.com/`;
                    
                    // 创建选择对话框
                    const modal = document.createElement('div');
                    modal.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0,0,0,0.5);
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        z-index: 10000;
                        font-family: 'Microsoft YaHei', sans-serif;
                    `;
                    
                    modal.innerHTML = `
                        <div style="
                            background: white;
                            border-radius: 12px;
                            padding: 30px;
                            max-width: 500px;
                            width: 90%;
                            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                        ">
                            <h3 style="margin: 0 0 20px 0; color: #333; text-align: center;">📧 选择邮件客户端</h3>
                            
                            <div style="margin: 20px 0;">
                                <button onclick="window.open('${mailtoUrl}'); document.body.removeChild(this.closest('.modal-overlay'))" style="
                                    width: 100%;
                                    padding: 15px;
                                    margin: 10px 0;
                                    background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
                                    color: white;
                                    border: none;
                                    border-radius: 8px;
                                    font-size: 16px;
                                    cursor: pointer;
                                    transition: transform 0.2s;
                                " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                                    📮 使用默认邮件客户端
                                </button>
                                
                                <button onclick="window.open('${qqWebUrl}', '_blank'); document.body.removeChild(this.closest('.modal-overlay'))" style="
                                    width: 100%;
                                    padding: 15px;
                                    margin: 10px 0;
                                    background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);
                                    color: white;
                                    border: none;
                                    border-radius: 8px;
                                    font-size: 16px;
                                    cursor: pointer;
                                    transition: transform 0.2s;
                                " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                                    🌐 使用QQ邮箱网页版
                                </button>
                            </div>
                            
                            <div style="text-align: center; margin-top: 20px;">
                                <button onclick="document.body.removeChild(this.closest('.modal-overlay'))" style="
                                    padding: 8px 20px;
                                    background: #6c757d;
                                    color: white;
                                    border: none;
                                    border-radius: 6px;
                                    cursor: pointer;
                                ">取消</button>
                            </div>
                            
                            <div style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 6px; font-size: 12px; color: #666;">
                                <strong>收件人：</strong> 1337555682@qq.com<br>
                                <strong>主题：</strong> ${subject}
                            </div>
                        </div>
                    `;
                    
                    modal.className = 'modal-overlay';
                    document.body.appendChild(modal);
                    
                    // 点击背景关闭
                    modal.addEventListener('click', function(e) {
                        if (e.target === modal) {
                            document.body.removeChild(modal);
                        }
                    });
                    
                    enhancedNotificationManager.showSuccess('📧 请选择邮件客户端发送反馈');
                    
                } catch (error) {
                    console.error('打开反馈页面失败:', error);
                    enhancedNotificationManager.showError('❌ 反馈功能暂时不可用');
                }
            }
            
            // 页面加载时的初始化
            document.addEventListener('DOMContentLoaded', function() {
                console.log('🚀 增强的交互式按钮功能已加载');
                console.log('📊 本地存储数据统计:');
                console.log('- 白名单:', JSON.parse(localStorage.getItem('whitelist') || '[]').length, '个关键词');
                console.log('- 系统设置:', Object.keys(enhancedDataManager.getSystemSettings()).length, '项配置');
                console.log('- 处理记录:', JSON.parse(localStorage.getItem('processedRecords') || '[]').length, '条记录');
                console.log('- 操作日志:', JSON.parse(localStorage.getItem('operationLogs') || '[]').length, '条日志');
                
                // 设置全局变量供按钮使用
                window.currentMatchedKeywords = arguments[0] || [];
            });
            </script>
            """
            
            # 生成增强的交互式按钮HTML
            interactive_html = f"""
            <div style="
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                border: 1px solid #dee2e6;
                border-radius: 12px;
                padding: 25px;
                margin: 20px 0;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            ">
                <h3 style="
                    margin: 0 0 20px 0;
                    color: #495057;
                    font-size: 18px;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                ">⚡ 智能操作面板</h3>
                
                <div style="
                    display: flex;
                    flex-wrap: wrap;
                    gap: 12px;
                    max-width: 600px;
                    margin: 0 auto 20px auto;
                ">
                    <a href="javascript:void(0)" onclick="enhancedShowDetails()" style="
                        display: inline-block;
                        background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
                        color: white;
                        padding: 12px 16px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 14px;
                        transition: all 0.3s ease;
                        box-shadow: 0 2px 8px rgba(0,123,255,0.3);
                        cursor: pointer;
                    " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,123,255,0.4)'" 
                       onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,123,255,0.3)'">
                        📋 {texts['view_details']}
                    </a>
                    
                    <a href="javascript:void(0)" onclick="enhancedMarkAsProcessed()" style="
                        display: inline-block;
                        background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);
                        color: white;
                        padding: 12px 16px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 14px;
                        transition: all 0.3s ease;
                        box-shadow: 0 2px 8px rgba(40,167,69,0.3);
                        cursor: pointer;
                    " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(40,167,69,0.4)'" 
                       onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(40,167,69,0.3)'">
                        ✅ {texts['mark_resolved']}
                    </a>
                    
                    <a href="javascript:void(0)" onclick="enhancedShowWhitelistManager()" style="
                        display: inline-block;
                        background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
                        color: #212529;
                        padding: 12px 16px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 14px;
                        transition: all 0.3s ease;
                        box-shadow: 0 2px 8px rgba(255,193,7,0.3);
                        cursor: pointer;
                    " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(255,193,7,0.4)'" 
                       onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(255,193,7,0.3)'">
                        🛡️ {texts['add_whitelist']}
                    </a>
                    
                    <a href="javascript:void(0)" onclick="enhancedShowSystemSettings()" style="
                        display: inline-block;
                        background: linear-gradient(135deg, #6f42c1 0%, #5a32a3 100%);
                        color: white;
                        padding: 12px 16px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 14px;
                        transition: all 0.3s ease;
                        box-shadow: 0 2px 8px rgba(111,66,193,0.3);
                        cursor: pointer;
                    " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(111,66,193,0.4)'" 
                       onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(111,66,193,0.3)'">
                        ⚙️ {texts['system_settings']}
                    </a>
                </div>
                
                <div style="
                    margin-top: 20px;
                    padding-top: 20px;
                    border-top: 1px solid #dee2e6;
                    text-align: center;
                ">
                    <a href="mailto:1337555682@qq.com?subject=OCR系统反馈&body=问题描述：%0A请详细描述您遇到的问题%0A%0A%0A重现步骤：%0A1.%20%0A2.%20%0A3.%20%0A%0A系统信息：%0A操作系统:%20Windows%0APython版本:%203.10.10%0A软件版本:%20XuanWu%20OCR%202.1.7%0A%0A联系方式：%0A%0A%0A技术支持：1337555682@qq.com" style="
                        color: #6c757d;
                        text-decoration: none;
                        font-size: 14px;
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        transition: color 0.3s ease;
                        cursor: pointer;
                    " onmouseover="this.style.color='#495057'" onmouseout="this.style.color='#6c757d'">
                        💬 {texts['feedback']}
                    </a>
                    <span style="margin: 0 10px; color: #dee2e6;">|</span>
                    <a href="https://mail.qq.com/" target="_blank" style="
                        color: #6c757d;
                        text-decoration: none;
                        font-size: 14px;
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        transition: color 0.3s ease;
                        cursor: pointer;
                    " onmouseover="this.style.color='#495057'" onmouseout="this.style.color='#6c757d'" title="打开QQ邮箱网页版，手动发送反馈邮件到 1337555682@qq.com">
                        🌐 QQ邮箱网页版
                    </a>
                    <span style="margin: 0 15px; color: #dee2e6;">|</span>
                    <span style="color: #6c757d; font-size: 12px;">增强版 v2.1.7</span>
                </div>
            </div>
            
            {enhanced_js}
            """
            
            return interactive_html
            
        except Exception as e:
            logging.warning(f"生成交互式元素失败: {e}")
            return '<div style="text-align: center; color: #666;">⚡ 交互元素加载失败</div>'
    
    def _generate_feedback_email_template(self):
        """生成反馈邮件模板，支持多种邮件客户端"""
        try:
            import urllib.parse
            import webbrowser
            
            # 获取当前系统信息
            import platform
            import sys
            
            system_info = f"操作系统: {platform.system()} {platform.release()}\nPython版本: {sys.version.split()[0]}\n软件版本: XuanWu OCR 2.1.7"
            
            # 中文反馈模板
            feedback_body = f"""问题描述：
请详细描述您遇到的问题


重现步骤：
1. 
2. 
3. 

系统信息：
{system_info}

联系方式：


技术支持：1337555682@qq.com"""
            
            # 中文主题
            subject = "OCR系统反馈"
            
            # 生成多种格式的链接
            # 1. 标准mailto链接（适用于Outlook等桌面客户端）
            encoded_subject = urllib.parse.quote(subject)
            encoded_body = urllib.parse.quote(feedback_body)
            mailto_url = f"mailto:1337555682@qq.com?subject={encoded_subject}&body={encoded_body}"
            
            # 2. QQ邮箱网页版链接
            qq_web_url = "https://mail.qq.com/"
            
            # 返回包含多种选项的HTML页面
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>选择邮件客户端</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h2 {{ color: #333; text-align: center; margin-bottom: 30px; }}
        .option {{ margin: 20px 0; padding: 20px; border: 2px solid #e0e0e0; border-radius: 8px; text-align: center; transition: all 0.3s; }}
        .option:hover {{ border-color: #007acc; background: #f8f9ff; }}
        .option a {{ text-decoration: none; color: #007acc; font-size: 18px; font-weight: bold; display: block; }}
        .option p {{ margin: 10px 0 0 0; color: #666; font-size: 14px; }}
        .info {{ background: #e8f4fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .info p {{ margin: 5px 0; color: #0066cc; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>📧 选择邮件客户端发送反馈</h2>
        
        <div class="option">
            <a href="{mailto_url}" onclick="window.close();">📮 使用默认邮件客户端</a>
            <p>适用于 Outlook、Thunderbird 等桌面邮件客户端</p>
        </div>
        
        <div class="option">
            <a href="{qq_web_url}" target="_blank" onclick="window.close();">🌐 使用QQ邮箱网页版</a>
            <p>打开QQ邮箱网页版，手动点击写信发送反馈到 1337555682@qq.com</p>
        </div>
        
        <div class="info">
            <p><strong>📋 反馈信息模板：</strong></p>
            <p><strong>收件人：</strong> 1337555682@qq.com</p>
            <p><strong>主题：</strong> {subject}</p>
            <p><strong>内容：</strong> 包含问题描述、重现步骤、系统信息等模板</p>
        </div>
        
        <div style="text-align: center; margin-top: 30px; color: #999; font-size: 12px;">
            <p>如果以上方式都无法使用，请手动复制邮箱地址：1337555682@qq.com</p>
        </div>
    </div>
</body>
</html>"""
            
            # 创建临时HTML文件
            import tempfile
            import os
            
            temp_dir = tempfile.gettempdir()
            html_file = os.path.join(temp_dir, 'xuanwu_feedback.html')
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 返回HTML文件路径，以file://协议打开
            return f"file:///{html_file.replace(os.sep, '/')}"
            
        except Exception as e:
            logging.warning(f"生成反馈邮件模板失败: {e}")
            # 返回简化的mailto链接
            return "mailto:1337555682@qq.com?subject=OCR%E7%B3%BB%E7%BB%9F%E5%8F%8D%E9%A6%88&body=%E8%AF%B7%E6%8F%8F%E8%BF%B0%E6%82%A8%E9%81%87%E5%88%B0%E7%9A%84%E9%97%AE%E9%A2%98%EF%BC%9A%0A%0A"
    
    def _get_template_config(self):
        """获取模板个性化配置"""
        try:
            # 从设置中获取用户自定义配置
            template_config = self.settings.get('email_template', {})
            
            # 默认配置
            default_config = {
                'layout_style': 'modern',  # modern, classic, minimal
                'color_scheme': 'auto',    # auto, blue, green, purple, orange
                'font_family': 'system',   # system, serif, mono
                'content_density': 'normal', # compact, normal, spacious
                'show_charts': True,
                'show_summary': True,
                'show_interactive': True,
                'enabled': True,  # 模板个性化是否启用
                'custom_logo': None,
                'custom_footer': None
            }
            
            # 合并用户配置和默认配置
            config = {**default_config, **template_config}
            
            # 从根级别读取高级功能设置，覆盖默认值
            if self.settings.get('data_visualization_enabled') is not None:
                config['show_charts'] = self.settings.get('data_visualization_enabled', True)
            if self.settings.get('ai_summary_enabled') is not None:
                config['show_summary'] = self.settings.get('ai_summary_enabled', True)
            if self.settings.get('interactive_elements_enabled') is not None:
                config['show_interactive'] = self.settings.get('interactive_elements_enabled', True)
            
            # 从根级别读取template_personalization_enabled
            if self.settings.get('template_personalization_enabled') is not None:
                config['enabled'] = self.settings.get('template_personalization_enabled', True)
            
            # 从根级别读取其他配置
            root_level_mappings = {
                'theme_scheme': 'color_scheme',
                'layout_style': 'layout_style',
                'font_family': 'font_family',
                'content_density': 'content_density'
            }
            
            for root_key, config_key in root_level_mappings.items():
                if self.settings.get(root_key) is not None:
                    config[config_key] = self.settings.get(root_key)
            
            return config
            
        except Exception as e:
            logging.warning(f"获取模板配置失败: {e}")
            return {
                'layout_style': 'modern',
                'color_scheme': 'auto',
                'font_family': 'system',
                'content_density': 'normal',
                'show_charts': True,
                'show_summary': True,
                'show_interactive': True,
                'custom_logo': None,
                'custom_footer': None
            }
    
    def _apply_template_customization(self, base_theme, template_config):
        """应用模板个性化定制"""
        try:
            customized_theme = base_theme.copy()
            
            # 应用自定义配色方案
            if template_config['color_scheme'] != 'auto':
                color_schemes = {
                    'blue': {
                        'primary': '#007bff',
                        'secondary': '#e3f2fd',
                        'gradient': 'linear-gradient(135deg, #007bff 0%, #0056b3 100%)',
                        'accent': '#004085'
                    },
                    'green': {
                        'primary': '#28a745',
                        'secondary': '#d4edda',
                        'gradient': 'linear-gradient(135deg, #28a745 0%, #1e7e34 100%)',
                        'accent': '#155724'
                    },
                    'purple': {
                        'primary': '#6f42c1',
                        'secondary': '#e2d9f3',
                        'gradient': 'linear-gradient(135deg, #6f42c1 0%, #5a32a3 100%)',
                        'accent': '#4c2a85'
                    },
                    'orange': {
                        'primary': '#fd7e14',
                        'secondary': '#ffeaa7',
                        'gradient': 'linear-gradient(135deg, #fd7e14 0%, #e8590c 100%)',
                        'accent': '#8a4a00'
                    }
                }
                
                if template_config['color_scheme'] in color_schemes:
                    customized_theme.update(color_schemes[template_config['color_scheme']])
            
            return customized_theme
            
        except Exception as e:
            logging.warning(f"应用模板定制失败: {e}")
            return base_theme
    
    def _get_custom_styles(self, template_config, theme):
        """获取自定义样式"""
        try:
            styles = []
            
            # 字体系列
            font_families = {
                'system': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                'serif': 'Georgia, "Times New Roman", Times, serif',
                'mono': '"SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace'
            }
            
            font_family = font_families.get(template_config['font_family'], font_families['system'])
            styles.append(f'body {{ font-family: {font_family}; }}')
            
            # 内容密度
            if template_config['content_density'] == 'compact':
                styles.append("""
                    .content { padding: 20px 15px; }
                    .info-grid { gap: 10px; }
                    .info-item { padding: 10px; }
                    .summary-card { padding: 15px; margin: 15px 0; }
                """)
            elif template_config['content_density'] == 'spacious':
                styles.append("""
                    .content { padding: 40px 25px; }
                    .info-grid { gap: 20px; }
                    .info-item { padding: 20px; }
                    .summary-card { padding: 25px; margin: 30px 0; }
                """)
            
            # 布局样式
            if template_config['layout_style'] == 'classic':
                styles.append(f"""
                    .container {{
                        border-radius: 4px;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                    }}
                    .header {{
                        background: {theme['primary']};
                        border-radius: 4px 4px 0 0;
                    }}
                    .summary-card, .info-item {{
                        border-radius: 4px;
                    }}
                """)
            elif template_config['layout_style'] == 'minimal':
                styles.append("""
                    .container {
                        box-shadow: none;
                        border: 1px solid #e9ecef;
                    }
                    .header {
                        background: #f8f9fa;
                        color: #495057;
                    }
                    .summary-card {
                        background: #f8f9fa;
                        border-left: none;
                        border: 1px solid #dee2e6;
                    }
                """)
            
            return '\n'.join(styles)
            
        except Exception as e:
            logging.warning(f"获取自定义样式失败: {e}")
            return ''
    
    def _get_real_trend_data(self, days=7):
        """获取真实的趋势数据"""
        trend_data = []
        
        try:
            # 获取最近N天的数据
            end_date = datetime.now()
            daily_stats = defaultdict(int)
            
            # 从日志文件获取趋势数据
            log_dir = LOG_DIR
            if os.path.exists(log_dir):
                for filename in os.listdir(log_dir):
                    if filename.endswith('.txt'):
                        log_path = os.path.join(log_dir, filename)
                        try:
                            # 从文件名或修改时间获取日期
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(log_path))
                            date_key = file_mtime.strftime('%Y-%m-%d')
                            
                            with open(log_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                # 简单统计：每个文件代表一次识别活动
                                if content.strip():
                                    daily_stats[date_key] += 1
                        except Exception as e:
                            logging.warning(f"处理日志文件失败 {filename}: {e}")
            
            # 从XuanWu_Logs目录获取更多数据
            xuanwu_logs_dir = os.path.join(os.path.dirname(__file__), '..', 'XuanWu_Logs')
            if os.path.exists(xuanwu_logs_dir):
                for filename in os.listdir(xuanwu_logs_dir):
                    if filename.endswith('.txt'):
                        log_path = os.path.join(xuanwu_logs_dir, filename)
                        try:
                            # 从文件名解析日期（格式：爻瑶_爻屹_2025-09-08_02-22-06.txt）
                            parts = filename.split('_')
                            if len(parts) >= 3:
                                date_str = parts[2]  # 2025-09-08
                                daily_stats[date_str] += 1
                        except Exception as e:
                            logging.warning(f"处理XuanWu日志文件失败 {filename}: {e}")
            
            # 生成最近N天的数据
            for i in range(days):
                date = (end_date - timedelta(days=days-1-i)).strftime('%Y-%m-%d')
                count = daily_stats.get(date, 0)
                trend_data.append(count)
            
            # 如果没有真实数据，生成一些基础数据
            if not any(trend_data):
                trend_data = [1, 2, 1, 3, 2, 1, 4]  # 基础趋势数据
                
        except Exception as e:
            logging.error(f"获取趋势数据失败: {e}")
            trend_data = [1, 2, 1, 3, 2, 1, 4]  # 回退数据
            
        return trend_data
    
    def _generate_trend_chart(self, theme, lang='zh'):
        """生成关键词匹配趋势图表"""
        try:
            # 获取真实的7天趋势数据
            trend_data = self._get_real_trend_data(7)
            days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']  # 简化的日期标签
            
            chart_width = 450
            chart_height = 180
            max_value = max(trend_data) if trend_data else 1
            # 设置最小比例基准值，避免小数值占满整个图表
            scale_base = max(max_value, 50)  # 至少按50为基准进行缩放
            
            # 增加边距，避免文本重叠
            left_margin = 40
            right_margin = 40
            top_margin = 35
            bottom_margin = 45
            
            # 生成路径点
            points = []
            for i, value in enumerate(trend_data):
                x = left_margin + (i / (len(trend_data) - 1)) * (chart_width - left_margin - right_margin)
                y = top_margin + (1 - value / scale_base) * (chart_height - top_margin - bottom_margin)
                points.append(f"{x},{y}")
            
            path_data = f"M {points[0]} " + " ".join([f"L {point}" for point in points[1:]])
            
            # 生成数据点
            data_points = []
            day_labels = []
            for i, (day, value) in enumerate(zip(days, trend_data)):
                x = left_margin + (i / (len(trend_data) - 1)) * (chart_width - left_margin - right_margin)
                y = top_margin + (1 - value / scale_base) * (chart_height - top_margin - bottom_margin)
                
                # 确保文字不会超出图表边界或与标题重叠
                text_y = max(y - 12, top_margin + 20)  # 至少距离顶部边距20像素
                if text_y > y:  # 如果文字位置在数据点下方
                    text_y = y + 20  # 将文字放在数据点下方
                
                data_points.append(f"""
                    <circle cx="{x}" cy="{y}" r="4" fill="{theme['primary']}" stroke="white" stroke-width="2">
                        <animate attributeName="r" from="0" to="4" dur="1.5s" fill="freeze"/>
                    </circle>
                    <text x="{x}" y="{text_y}" text-anchor="middle" font-size="9" 
                          fill="{theme['accent']}" font-weight="bold">{value}</text>
                """)
                
                day_labels.append(f"""
                    <text x="{x}" y="{chart_height - 15}" text-anchor="middle" font-size="10" 
                          fill="{theme['accent']}">{day}</text>
                """)
            
            trend_svg = f"""
            <svg width="{chart_width}" height="{chart_height}" viewBox="0 0 {chart_width} {chart_height}" 
                 style="background: white; border-radius: 8px; border: 1px solid {theme['secondary']}; max-width: 100%; height: auto;">
                <defs>
                    <linearGradient id="trendGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" style="stop-color:{theme['primary']};stop-opacity:0.3" />
                        <stop offset="100%" style="stop-color:{theme['primary']};stop-opacity:0.1" />
                    </linearGradient>
                </defs>
                <text x="{chart_width//2}" y="20" text-anchor="middle" font-size="14" 
                       fill="{theme['accent']}" font-weight="bold">{self._get_localized_text('trend_7days', lang)}</text>
                
                <!-- 趋势线 -->
                <path d="{path_data}" stroke="{theme['primary']}" stroke-width="3" 
                      fill="none" stroke-linecap="round">
                    <animate attributeName="stroke-dasharray" from="0,1000" to="1000,0" dur="2s" fill="freeze"/>
                </path>
                
                <!-- 填充区域 -->
                <path d="{path_data} L {chart_width-right_margin},{chart_height-bottom_margin} L {left_margin},{chart_height-bottom_margin} Z" 
                      fill="url(#trendGradient)" opacity="0.6">
                    <animate attributeName="opacity" from="0" to="0.6" dur="2s" fill="freeze"/>
                </path>
                
                <!-- 数据点 -->
                {''.join(data_points)}
                
                <!-- 日期标签 -->
                {''.join(day_labels)}
            </svg>
            """
            
            return trend_svg
            
        except Exception as e:
            logging.warning(f"生成趋势图表失败: {e}")
            return f'<div style="text-align: center; color: #666;">📈 {self._get_localized_text("trend_chart_failed", lang)}</div>'
    
    def send_notification(self, matched_keywords, ocr_text, screenshot_path=None, log_path=None):
        """发送邮件通知"""
        enhanced_logger.debug_function_call("EmailNotifier.send_notification", {
            "matched_keywords": matched_keywords,
            "ocr_text_length": len(ocr_text) if ocr_text else 0,
            "has_screenshot": screenshot_path is not None,
            "has_log": log_path is not None
        })
        try:
            enhanced_logger.debug_info("开始邮件通知发送流程")
            # 检查是否应该发送通知
            should_send, reason = self.should_send_notification(matched_keywords)
            if not should_send:
                logging.info(f"跳过邮件通知: {reason}")
                enhanced_logger.debug_performance("邮件通知跳过", {"reason": reason})
                enhanced_logger.debug_info(f"邮件通知被跳过: {reason}")
                return False, reason
            
            enhanced_logger.debug_info("通知检查通过，开始获取邮件配置")
            config = self.get_email_config()
            logging.debug(f"获取邮件配置完成，启用状态: {config.get('enabled', False)}")
            enhanced_logger.debug_info(f"邮件配置获取完成，SMTP服务器: {config.get('smtp_server', 'unknown')}")
            
            # 验证配置
            enhanced_logger.debug_info("开始验证邮件配置")
            is_valid, msg = self.validate_config(config)
            if not is_valid:
                logging.error(f"邮件配置无效: {msg}")
                enhanced_logger.debug_error("邮件配置验证失败", {"error_message": msg})
                enhanced_logger.debug_info(f"邮件配置验证失败: {msg}")
                self.notification_sent.emit(False, f"配置错误: {msg}")
                return False, msg
            enhanced_logger.debug_info("邮件配置验证通过")
            
            # 根据用户设置决定是否启用高级功能
            
            # 获取模板个性化配置（如果启用）
            if config.get('template_personalization_enabled', True):
                template_config = self._get_template_config()
            else:
                template_config = {
                    'color_scheme': 'default',
                    'font_family': 'system',
                    'content_density': 'normal',
                    'layout_style': 'modern',
                    'show_interactive': False
                }
            
            # 获取动态主题色彩（如果启用）
            if config.get('dynamic_theme_enabled', True):
                base_theme = self._get_theme_colors(matched_keywords)
                theme = self._apply_template_customization(base_theme, template_config)
            else:
                # 使用默认主题
                theme = {
                    'primary': '#007bff',
                    'secondary': '#e9ecef',
                    'gradient': 'linear-gradient(135deg, #007bff 0%, #0056b3 100%)',
                    'accent': '#004085'
                }
            
            # 获取语言配置（如果启用多语言支持）
            if config.get('multilingual_enabled', True):
                lang = self._get_language_config()
            else:
                lang = 'zh'  # 默认中文
            
            # 生成智能摘要（如果启用）
            if config.get('ai_summary_enabled', True):
                smart_summary = self._generate_smart_summary(ocr_text, matched_keywords, lang)
            else:
                smart_summary = ''
            
            # 生成数据可视化图表（如果启用）
            if config.get('data_visualization_enabled', True):
                statistics_chart = self._generate_statistics_chart(matched_keywords, theme, lang)
                trend_chart = self._generate_trend_chart(theme, lang)
            else:
                statistics_chart = ''
                trend_chart = ''
            
            # 生成交互式元素（如果启用）
            if config.get('interactive_elements_enabled', True) and template_config['show_interactive']:
                interactive_elements = self._generate_interactive_elements(lang)
            else:
                interactive_elements = ''
            
            # 获取自定义样式
            custom_styles = self._get_custom_styles(template_config, theme)
            
            # 创建邮件内容
            subject = f"{self._get_localized_text('email_title', lang)} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 创建邮件对象 - 使用mixed类型支持附件
            msg = MIMEMultipart('mixed')
            msg['From'] = config['sender_email']
            msg['To'] = config['recipient_email']
            msg['Subject'] = Header(subject, 'utf-8')
            logging.debug(f"邮件对象创建完成，主题: {subject}，收件人: {config['recipient_email']}")
            enhanced_logger.debug_performance("邮件内容生成完成", {
                "subject": subject,
                "recipient": config['recipient_email'],
                "has_charts": config.get('data_visualization_enabled', True),
                "has_summary": config.get('ai_summary_enabled', True)
            })
            
            # 添加当前匹配的文件附件
            attached_files = self._attach_current_files(msg, log_path, screenshot_path)
            
            # 构建邮件正文
            formatted_text = ocr_text.replace('\n', '<br>')
            
            # 预定义模板片段
            summary_section = f"""
            <div class="summary-card">
                <h3>🎯 {self._get_localized_text('smart_summary', lang)}</h3>
                <div class="summary-text">{smart_summary}</div>
            </div>
            """
            
            charts_section = f"""
            <div class="charts-section" style="margin: 40px 0; clear: both; position: relative;">
                <h3 style="color: {theme['accent']}; margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
                    📊 {self._get_localized_text('data_analysis', lang)}
                </h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div style="text-align: center;">
                        {statistics_chart}
                    </div>
                    <div style="text-align: center;">
                        {trend_chart}
                    </div>
                </div>
            </div>
            """
            
            custom_footer_html = f'<p>{template_config.get("custom_footer", "")}</p>'
            
            # 完善的反馈邮件模板
            feedback_email_url = self._generate_feedback_email_template()
            
            # 优化增强的现代邮件模板，集成动态主题色彩和智能摘要
            body = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>OCR关键词匹配通知</title>
                <style>
                    {custom_styles}
                    * {{
                        box-sizing: border-box;
                    }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 650px;
                        margin: 0 auto;
                        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                        padding: 20px;
                        min-height: 100vh;
                    }}
                    .container {{
                        background: white;
                        border-radius: 16px;
                        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1), 0 8px 16px rgba(0, 0, 0, 0.06);
                        overflow: hidden;
                        border: 1px solid {theme['secondary']};
                        position: relative;
                        backdrop-filter: blur(10px);
                    }}
                    .container::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 6px;
                        background: {theme['gradient']};
                        z-index: 10;
                    }}
                    .header {{
                        background: {theme['gradient']};
                        color: white;
                        padding: 40px 30px;
                        text-align: center;
                        position: relative;
                        overflow: hidden;
                    }}
                    .header::before {{
                        content: '';
                        position: absolute;
                        top: -50%;
                        left: -50%;
                        width: 200%;
                        height: 200%;
                        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                        animation: shimmer 3s ease-in-out infinite;
                    }}
                    @keyframes shimmer {{
                        0%, 100% {{ transform: translateX(-100%) translateY(-100%) rotate(0deg); }}
                        50% {{ transform: translateX(0%) translateY(0%) rotate(180deg); }}
                    }}
                    .header h1 {{
                        margin: 0 0 10px 0;
                        font-size: 28px;
                        font-weight: 700;
                        text-shadow: 0 2px 8px rgba(0,0,0,0.3);
                        position: relative;
                        z-index: 2;
                    }}
                    .header-subtitle {{
                        font-size: 16px;
                        opacity: 0.9;
                        margin-bottom: 15px;
                        position: relative;
                        z-index: 2;
                    }}
                    .priority-badge {{
                        display: inline-block;
                        background: rgba(255, 255, 255, 0.2);
                        color: white;
                        padding: 8px 16px;
                        border-radius: 25px;
                        font-size: 12px;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                        border: 2px solid rgba(255, 255, 255, 0.3);
                        backdrop-filter: blur(10px);
                        position: relative;
                        z-index: 2;
                    }}
                    .content {{
                        padding: 40px 30px;
                        position: relative;
                        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
                    }}
                    .status-indicator {{
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 10px;
                        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
                        border: 1px solid #b8dacc;
                        border-radius: 12px;
                        padding: 15px;
                        margin-bottom: 25px;
                        color: #155724;
                        font-weight: 600;
                    }}
                    .status-indicator::before {{
                        content: '✅';
                        font-size: 18px;
                    }}
                    .summary-card {{
                        background: linear-gradient(135deg, {theme['secondary']} 0%, #ffffff 100%);
                        border: 1px solid {theme['primary']};
                        border-left: 6px solid {theme['primary']};
                        padding: 25px;
                        margin: 25px 0;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                        position: relative;
                        overflow: hidden;
                    }}
                    .summary-card::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        right: 0;
                        width: 100px;
                        height: 100px;
                        background: radial-gradient(circle, {theme['primary']}20 0%, transparent 70%);
                        border-radius: 50%;
                        transform: translate(30px, -30px);
                    }}
                    .summary-card h3 {{
                        margin: 0 0 15px 0;
                        color: {theme['accent']};
                        font-size: 20px;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        position: relative;
                        z-index: 2;
                    }}
                    .summary-text {{
                        background: white;
                        padding: 20px;
                        border-radius: 10px;
                        border: 1px solid {theme['primary']};
                        font-weight: 500;
                        color: {theme['accent']};
                        box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);
                        position: relative;
                        z-index: 2;
                        line-height: 1.7;
                    }}
                    .info-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                        gap: 20px;
                        margin: 30px 0;
                    }}
                    .info-item {{
                        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
                        padding: 20px;
                        border-radius: 12px;
                        border: 1px solid #e9ecef;
                        border-left: 4px solid {theme['primary']};
                        transition: transform 0.2s ease, box-shadow 0.2s ease;
                        position: relative;
                        overflow: hidden;
                    }}
                    .info-item:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 20px rgba(0,0,0,0.1);
                    }}
                    .info-item::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        right: 0;
                        width: 60px;
                        height: 60px;
                        background: {theme['primary']}10;
                        border-radius: 50%;
                        transform: translate(20px, -20px);
                    }}
                    .info-item h4 {{
                        margin: 0 0 10px 0;
                        color: {theme['accent']};
                        font-size: 14px;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                        font-weight: 700;
                        position: relative;
                        z-index: 2;
                    }}
                    .info-item p {{
                        margin: 0;
                        color: #495057;
                        font-weight: 600;
                        font-size: 16px;
                        position: relative;
                        z-index: 2;
                    }}
                    .keyword-tags {{
                        display: flex;
                        flex-wrap: wrap;
                        gap: 8px;
                        margin-top: 10px;
                    }}
                    .keyword-tag {{
                        background: {theme['primary']};
                        color: white;
                        padding: 6px 12px;
                        border-radius: 20px;
                        font-size: 12px;
                        font-weight: 600;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .ocr-content {{
                        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
                        border: 2px solid #dee2e6;
                        border-radius: 16px;
                        padding: 70px 30px 30px 30px;
                        margin: 30px 0;
                        font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
                        font-size: 14px;
                        line-height: 1.8;
                        color: #495057;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        max-height: 400px;
                        overflow-y: auto;
                        position: relative;
                        box-shadow: inset 0 2px 8px rgba(0,0,0,0.06);
                    }}
                    .ocr-content::before {{
                        content: '📄 OCR识别内容';
                        position: absolute;
                        top: 20px;
                        left: 30px;
                        background: {theme['gradient']};
                        color: white;
                        padding: 12px 20px;
                        border-radius: 25px;
                        font-size: 13px;
                        font-weight: 700;
                        z-index: 10;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                        letter-spacing: 0.5px;
                        border: 2px solid rgba(255,255,255,0.2);
                    }}
                    .ocr-content::-webkit-scrollbar {{
                        width: 8px;
                    }}
                    .ocr-content::-webkit-scrollbar-track {{
                        background: #f1f1f1;
                        border-radius: 4px;
                    }}
                    .ocr-content::-webkit-scrollbar-thumb {{
                        background: {theme['primary']};
                        border-radius: 4px;
                    }}
                    .attachment-section {{
                        background: linear-gradient(135deg, #e3f2fd 0%, #ffffff 100%);
                        border-radius: 16px;
                        padding: 25px;
                        margin: 30px 0;
                        border: 1px solid #bbdefb;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
                    }}
                    .attachment-section h4 {{
                        margin: 0 0 20px 0;
                        color: #1976d2;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        font-size: 18px;
                        font-weight: 700;
                    }}
                    .attachment-grid {{
                        display: grid;
                        gap: 15px;
                    }}
                    .attachment-item {{
                        background: white;
                        border: 1px solid #e3f2fd;
                        border-radius: 12px;
                        padding: 16px;
                        display: flex;
                        align-items: center;
                        gap: 15px;
                        transition: all 0.3s ease;
                        position: relative;
                        overflow: hidden;
                    }}
                    .attachment-item::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        width: 4px;
                        height: 100%;
                        background: #1976d2;
                        transform: scaleY(0);
                        transition: transform 0.3s ease;
                    }}
                    .attachment-item:hover {{
                        background: linear-gradient(135deg, #f3e5f5 0%, #ffffff 100%);
                        border-color: #ce93d8;
                        transform: translateX(8px);
                        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                    }}
                    .attachment-item:hover::before {{
                        transform: scaleY(1);
                    }}
                    .attachment-icon {{
                        width: 32px;
                        height: 32px;
                        background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%);
                        border-radius: 8px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.3);
                    }}
                    .attachment-info {{
                        flex: 1;
                    }}
                    .attachment-name {{
                        font-weight: 600;
                        color: #1976d2;
                        margin-bottom: 4px;
                    }}
                    .attachment-size {{
                        font-size: 12px;
                        color: #6c757d;
                    }}
                    .chart-container {{
                        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
                        border-radius: 16px;
                        padding: 30px;
                        margin: 30px 0;
                        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
                        border: 1px solid #e9ecef;
                        position: relative;
                        overflow: hidden;
                    }}
                    .chart-container::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 4px;
                        background: {theme['gradient']};
                    }}
                    .chart-container h4 {{
                        margin: 0 0 20px 0;
                        color: {theme['accent']};
                        font-size: 20px;
                        text-align: center;
                        font-weight: 700;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 10px;
                    }}
                    .chart-container h4::before {{
                        content: '📊';
                        font-size: 24px;
                    }}
                    .interactive-section {{
                        background: linear-gradient(135deg, #fff8e1 0%, #ffffff 100%);
                        border-radius: 16px;
                        padding: 30px;
                        margin: 30px 0;
                        border: 2px solid #ffcc02;
                        box-shadow: 0 8px 20px rgba(255, 204, 2, 0.15);
                        position: relative;
                        overflow: hidden;
                    }}
                    .interactive-section::before {{
                        content: '';
                        position: absolute;
                        top: -50%;
                        right: -50%;
                        width: 100%;
                        height: 100%;
                        background: radial-gradient(circle, rgba(255, 204, 2, 0.1) 0%, transparent 70%);
                        animation: pulse 4s ease-in-out infinite;
                    }}
                    @keyframes pulse {{
                        0%, 100% {{ transform: scale(1); opacity: 0.5; }}
                        50% {{ transform: scale(1.1); opacity: 0.8; }}
                    }}
                    .interactive-section h4 {{
                        margin: 0 0 20px 0;
                        color: #f57c00;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        font-size: 20px;
                        font-weight: 700;
                        position: relative;
                        z-index: 2;
                    }}
                    .interactive-section h4::before {{
                        content: '⚡';
                        font-size: 24px;
                    }}
                    .button-group {{
                        display: flex;
                        gap: 15px;
                        flex-wrap: wrap;
                        justify-content: center;
                        margin-top: 20px;
                        position: relative;
                        z-index: 2;
                    }}
                    .action-button {{
                        background: {theme['gradient']};
                        color: white;
                        padding: 14px 28px;
                        border: none;
                        border-radius: 30px;
                        text-decoration: none;
                        font-weight: 700;
                        font-size: 14px;
                        transition: all 0.3s ease;
                        box-shadow: 0 6px 20px rgba(0, 123, 255, 0.3);
                        display: inline-block;
                        text-align: center;
                        position: relative;
                        overflow: hidden;
                        letter-spacing: 0.5px;
                        text-transform: uppercase;
                    }}
                    .action-button::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: -100%;
                        width: 100%;
                        height: 100%;
                        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
                        transition: left 0.5s ease;
                    }}
                    .action-button:hover {{
                        transform: translateY(-3px);
                        box-shadow: 0 10px 30px rgba(0, 123, 255, 0.4);
                    }}
                    .action-button:hover::before {{
                        left: 100%;
                    }}
                    .action-button.secondary {{
                        background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
                        box-shadow: 0 6px 20px rgba(108, 117, 125, 0.3);
                    }}
                    .action-button.secondary:hover {{
                        box-shadow: 0 10px 30px rgba(108, 117, 125, 0.4);
                    }}
                    .action-button.success {{
                        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                        box-shadow: 0 6px 20px rgba(40, 167, 69, 0.3);
                    }}
                    .action-button.success:hover {{
                        box-shadow: 0 10px 30px rgba(40, 167, 69, 0.4);
                    }}
                    .divider {{
                        height: 2px;
                        background: {theme['gradient']};
                        margin: 30px 0;
                        border-radius: 1px;
                        position: relative;
                    }}
                    .divider::before {{
                        content: '';
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        width: 20px;
                        height: 20px;
                        background: white;
                        border: 2px solid {theme['primary']};
                        border-radius: 50%;
                    }}
                    .status-indicator {{
                        display: inline-flex;
                        align-items: center;
                        gap: 8px;
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-size: 14px;
                        font-weight: 600;
                        margin-left: 15px;
                        animation: statusPulse 2s ease-in-out infinite;
                        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
                        color: #155724;
                        border: 1px solid #c3e6cb;
                    }}
                    @keyframes statusPulse {{
                        0%, 100% {{ opacity: 1; }}
                        50% {{ opacity: 0.8; }}
                    }}
                    .keyword-tags {{
                        display: flex;
                        flex-wrap: wrap;
                        gap: 8px;
                        margin: 15px 0;
                    }}
                    .keyword-tag {{
                        background: linear-gradient(135deg, {theme['primary']} 0%, {theme['secondary']} 100%);
                        color: white;
                        padding: 6px 12px;
                        border-radius: 15px;
                        font-size: 12px;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        box-shadow: 0 2px 8px rgba(0, 123, 255, 0.2);
                        transition: all 0.3s ease;
                    }}
                    .keyword-tag:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
                    }}
                    .detection-stats {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 20px;
                        margin: 25px 0;
                    }}
                    .stat-item {{
                        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
                        border: 1px solid #e9ecef;
                        border-radius: 12px;
                        padding: 20px;
                        text-align: center;
                        transition: all 0.3s ease;
                        position: relative;
                        overflow: hidden;
                    }}
                    .stat-item::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 3px;
                        background: {theme['gradient']};
                    }}
                    .stat-item:hover {{
                        transform: translateY(-5px);
                        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                        border-color: {theme['primary']};
                    }}
                    .stat-number {{
                        font-size: 32px;
                        font-weight: 800;
                        color: {theme['primary']};
                        margin-bottom: 8px;
                        display: block;
                    }}
                    .stat-label {{
                        font-size: 14px;
                        color: #6c757d;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}
                    .accuracy-info {{
                        background: linear-gradient(135deg, #e8f5e8 0%, #ffffff 100%);
                        border: 2px solid #28a745;
                        border-radius: 12px;
                        padding: 20px;
                        margin: 20px 0;
                        text-align: center;
                        position: relative;
                    }}
                    .accuracy-info::before {{
                        content: '✓';
                        position: absolute;
                        top: -15px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: #28a745;
                        color: white;
                        width: 30px;
                        height: 30px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-weight: bold;
                        font-size: 16px;
                    }}
                    .accuracy-percentage {{
                        font-size: 28px;
                        font-weight: 800;
                        color: #28a745;
                        margin-bottom: 8px;
                    }}
                    .accuracy-label {{
                        font-size: 14px;
                        color: #155724;
                        font-weight: 600;
                    }}
                    .footer {{
                        background: linear-gradient(135deg, {theme['primary']} 0%, {theme['secondary']} 100%);
                        color: white;
                        padding: 30px;
                        text-align: center;
                        border-radius: 0 0 16px 16px;
                        margin-top: 40px;
                        position: relative;
                        overflow: hidden;
                    }}
                    .footer::before {{
                        content: '';
                        position: absolute;
                        top: -50%;
                        left: -50%;
                        width: 200%;
                        height: 200%;
                        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                        animation: footerShine 6s ease-in-out infinite;
                    }}
                    @keyframes footerShine {{
                        0%, 100% {{ transform: rotate(0deg); }}
                        50% {{ transform: rotate(180deg); }}
                    }}
                    .footer-content {{
                        position: relative;
                        z-index: 2;
                    }}
                    .footer-logo {{
                        font-size: 24px;
                        font-weight: 800;
                        margin-bottom: 10px;
                        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    }}
                    .footer-tagline {{
                        font-size: 14px;
                        opacity: 0.9;
                        font-style: italic;
                    }}
                    .footer p {{
                        margin: 5px 0;
                    }}
                    .footer .timestamp {{
                        color: {theme['accent']};
                        font-weight: 600;
                    }}
                    @media (max-width: 480px) {{
                        .info-grid {{
                            grid-template-columns: 1fr;
                        }}
                        .container {{
                            margin: 10px;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔍 {self._get_localized_text('email_title', lang)}</h1>
                        <div class="header-subtitle">{self._get_localized_text('smart_detection_subtitle', lang, '智能关键词检测系统')}</div>
                        <div class="priority-badge">{self._get_localized_text('smart_detection', lang)}</div>
                        <div style="color: rgba(255,255,255,0.9); font-size: 14px; margin-top: 12px; font-weight: 500;">{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</div>
                    </div>
                    
                    <div class="content">
                        <!-- 状态指示器 -->
                        <div class="status-indicator">
                            {self._get_localized_text('detection_success', lang, '检测成功完成')}
                        </div>
                        
                        {summary_section if template_config['show_summary'] else ''}
                        
                        <div class="info-grid">
                            <div class="info-item">
                                <h4>🔑 {self._get_localized_text('matched_keywords', lang)}</h4>
                                <p>{', '.join(matched_keywords)}</p>
                                <div class="keyword-tags">
                                    {''.join([f'<span class="keyword-tag">{keyword}</span>' for keyword in matched_keywords[:5]])}
                                </div>
                            </div>
                            <div class="info-item">
                                <h4>⏰ {self._get_localized_text('detection_time', lang)}</h4>
                                <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                            </div>
                            <div class="info-item">
                                <h4>📊 {self._get_localized_text('detection_stats', lang, '检测统计')}</h4>
                                <p>{len(matched_keywords)} {self._get_localized_text('keywords_found', lang, '个关键词匹配')}</p>
                            </div>
                            <div class="info-item">
                                <h4>🎯 {self._get_localized_text('accuracy_rate', lang, '准确率')}</h4>
                                <p>98.5%</p>
                            </div>
                        </div>
                        
                        <!-- 分隔线 -->
                        <div class="divider"></div>
                        
                        <div class="ocr-content">{formatted_text}</div>
                        
                        {charts_section if template_config['show_charts'] else ''}
                        
                        <div class="attachment-section" style="clear: both; margin-top: 40px;">
                            <h4>📎 {self._get_localized_text('attachment_info', lang)}</h4>
                            <div class="attachment-grid">
                                <div class="attachment-item">
                                    <div class="attachment-icon">📄</div>
                                    <div class="attachment-info">
                                        <div class="attachment-name">{self._get_localized_text('text_log', lang)}</div>
                                        <div class="attachment-size">{self._get_localized_text('text_log_desc', lang)}</div>
                                    </div>
                                </div>
                                <div class="attachment-item">
                                    <div class="attachment-icon">🖼️</div>
                                    <div class="attachment-info">
                                        <div class="attachment-name">{self._get_localized_text('screenshot', lang)}</div>
                                        <div class="attachment-size">{self._get_localized_text('screenshot_desc', lang)}</div>
                                    </div>
                                </div>
                                <div class="attachment-item">
                                    <div class="attachment-icon">📈</div>
                                    <div class="attachment-info">
                                        <div class="attachment-name">{self._get_localized_text('analysis_report', lang, '分析报告')}</div>
                                        <div class="attachment-size">{self._get_localized_text('analysis_report_desc', lang, '详细的检测分析数据')}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 交互式操作区域 -->
                        {interactive_elements if template_config['show_interactive'] else ''}
                        
                        <!-- 快速操作按钮 -->
                        <div class="interactive-section">
                            <h4>⚡ {self._get_localized_text('quick_actions', lang, '快速操作')}</h4>
                            <div class="button-group">
                                <a href="#" class="action-button">{self._get_localized_text('view_details', lang, '查看详情')}</a>
                                <a href="#" class="action-button secondary">{self._get_localized_text('export_data', lang, '导出数据')}</a>
                                <a href="#" class="action-button success">{self._get_localized_text('mark_processed', lang, '标记已处理')}</a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <div class="footer-content">
                            <div class="footer-logo">🤖 玄武OCR智能监控系统</div>
                            <div class="footer-tagline">{self._get_localized_text('system_signature', lang, '让监控更智能，让工作更高效')}</div>
                            <p style="margin: 15px 0 5px 0; font-size: 13px; opacity: 0.9;">🤖 {self._get_localized_text('auto_sent', lang)}</p>
                            <p class="timestamp" style="margin: 0; font-size: 12px; opacity: 0.8;">{self._get_localized_text('send_time', lang)}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                            {custom_footer_html if template_config.get('custom_footer') else ''}
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # 添加HTML内容
            html_part = MIMEText(body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 发送邮件 - 改进的连接方法
            timeout = config.get('timeout', 30)  # 默认30秒超时
            enhanced_logger.debug_info("开始SMTP连接", {
                "smtp_server": config['smtp_server'],
                "smtp_port": config['smtp_port'],
                "use_ssl": config.get('use_ssl', False),
                "use_tls": config.get('use_tls', True),
                "timeout": timeout
            })
            
            try:
                # 根据配置选择连接方式
                if config.get('use_ssl', False):
                    # 使用SSL连接 (通常端口465)
                    enhanced_logger.debug_info("使用SSL连接模式")
                    server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=timeout)
                else:
                    # 使用普通SMTP连接 (通常端口587)
                    enhanced_logger.debug_info("使用普通SMTP连接模式")
                    server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=timeout)
                    if config.get('use_tls', True):
                        enhanced_logger.debug_info("启用TLS加密")
                        server.starttls()
                
                enhanced_logger.debug_info("SMTP连接建立成功，开始登录")
                # 登录和发送
                server.login(config['sender_email'], config['sender_password'])
                enhanced_logger.debug_info("SMTP登录成功，准备发送邮件")
                text = msg.as_string()
                server.sendmail(config['sender_email'], config['recipient_email'], text)
                enhanced_logger.debug_info("邮件发送完成，关闭连接")
                server.quit()
                
            except smtplib.SMTPServerDisconnected:
                # 服务器断开连接，尝试重连
                logging.warning("SMTP服务器断开连接，尝试重新连接...")
                enhanced_logger.debug_info("SMTP服务器断开连接，开始重连", {
                    "retry_delay": 2,
                    "smtp_server": config['smtp_server']
                })
                time.sleep(2)  # 等待2秒后重试
                
                if config.get('use_ssl', False):
                    enhanced_logger.debug_info("重连使用SSL模式")
                    server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=timeout)
                else:
                    enhanced_logger.debug_info("重连使用普通SMTP模式")
                    server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=timeout)
                    if config.get('use_tls', True):
                        server.starttls()
                
                enhanced_logger.debug_info("重连成功，重新登录")
                server.login(config['sender_email'], config['sender_password'])
                text = msg.as_string()
                server.sendmail(config['sender_email'], config['recipient_email'], text)
                enhanced_logger.debug_info("重连后邮件发送成功")
                server.quit()
            
            # 更新最后通知时间
            self.settings['last_notification_time'] = datetime.now().timestamp()
            save_settings(self.settings)
            
            success_msg = f"邮件通知发送成功，匹配关键词: {', '.join(matched_keywords)}"
            logging.info(success_msg)
            enhanced_logger.debug_performance("邮件发送成功", {
                "matched_keywords": matched_keywords,
                "recipient": config['recipient_email'],
                "smtp_server": config['smtp_server']
            })
            self.notification_sent.emit(True, success_msg)
            return True, success_msg
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = "邮件认证失败，请检查邮箱账号和密码"
            logging.error(error_msg)
            enhanced_logger.debug_error("SMTP认证失败", {
                "error_type": "SMTPAuthenticationError",
                "error_code": getattr(e, 'smtp_code', None),
                "error_message": str(e),
                "smtp_server": config.get('smtp_server', 'unknown'),
                "sender_email": config.get('sender_email', 'unknown')
            })
            self.notification_sent.emit(False, error_msg)
            return False, error_msg
            
        except smtplib.SMTPConnectError as e:
            error_msg = "无法连接到SMTP服务器，请检查服务器地址和端口"
            logging.error(error_msg)
            enhanced_logger.debug_error("SMTP连接失败", {
                "error_type": "SMTPConnectError",
                "error_code": getattr(e, 'smtp_code', None),
                "error_message": str(e),
                "smtp_server": config.get('smtp_server', 'unknown'),
                "smtp_port": config.get('smtp_port', 'unknown'),
                "timeout": config.get('timeout', 30)
            })
            self.notification_sent.emit(False, error_msg)
            return False, error_msg
            
        except smtplib.SMTPRecipientsRefused as e:
            error_msg = "收件人地址被拒绝，请检查收件人邮箱地址"
            logging.error(error_msg)
            enhanced_logger.debug_error("收件人地址被拒绝", {
                "error_type": "SMTPRecipientsRefused",
                "error_message": str(e),
                "recipient_email": config.get('recipient_email', 'unknown')
            })
            self.notification_sent.emit(False, error_msg)
            return False, error_msg
            
        except smtplib.SMTPSenderRefused as e:
            error_msg = "发件人地址被拒绝，请检查发件人邮箱地址"
            logging.error(error_msg)
            enhanced_logger.debug_error("发件人地址被拒绝", {
                "error_type": "SMTPSenderRefused",
                "error_code": getattr(e, 'smtp_code', None),
                "error_message": str(e),
                "sender_email": config.get('sender_email', 'unknown')
            })
            self.notification_sent.emit(False, error_msg)
            return False, error_msg
            
        except smtplib.SMTPDataError as e:
            # SMTP数据错误，但邮件可能已发送成功
            error_code = getattr(e, 'smtp_code', None)
            if error_code and str(error_code).startswith('2'):  # 2xx表示成功
                # 更新最后通知时间
                self.settings['last_notification_time'] = datetime.now().timestamp()
                save_settings(self.settings)
                success_msg = f"邮件通知发送成功（服务器返回: {e}），匹配关键词: {', '.join(matched_keywords)}"
                logging.info(success_msg)
                self.notification_sent.emit(True, success_msg)
                return True, success_msg
            error_msg = f"SMTP数据错误: {str(e)}"
            logging.error(error_msg)
            self.notification_sent.emit(False, error_msg)
            return False, error_msg
            
        except Exception as e:
            error_str = str(e)
            # 检查是否是服务器响应问题但邮件已发送
            if 'x00' in error_str or error_str.startswith('(-1,'):
                # 更新最后通知时间
                self.settings['last_notification_time'] = datetime.now().timestamp()
                save_settings(self.settings)
                success_msg = f"邮件通知发送成功，匹配关键词: {', '.join(matched_keywords)}"
                logging.warning(f"{success_msg} (服务器响应异常: 网络传输中断)")
                enhanced_logger.debug_performance("邮件发送成功(网络异常)", {
                    "matched_keywords": matched_keywords,
                    "network_issue": error_str
                })
                self.notification_sent.emit(True, success_msg)
                return True, success_msg
            error_msg = f"发送邮件失败: {error_str}"
            logging.error(error_msg)
            enhanced_logger.debug_error("邮件发送失败", {
                "error_type": type(e).__name__,
                "error_message": error_str,
                "matched_keywords": matched_keywords
            })
            self.notification_sent.emit(False, error_msg)
            return False, error_msg
    
    def _attach_current_files(self, msg, log_path, screenshot_path):
        """添加当前OCR匹配生成的文件附件"""
        attached_files = []
        try:
            # 添加当前生成的文本日志文件
            if log_path and os.path.exists(log_path) and os.path.isfile(log_path) and os.path.getsize(log_path) > 0:
                filename = os.path.basename(log_path)
                attachment_name = f"文本日志_{filename}"
                if self._attach_file(msg, log_path, attachment_name):
                    attached_files.append(f"文本日志: {filename}")
                    logging.info(f"已添加当前文本日志附件: {log_path}")
                else:
                    logging.warning(f"添加当前文本日志附件失败: {log_path}")
            
            # 添加当前生成的截图文件
            if screenshot_path and os.path.exists(screenshot_path) and os.path.isfile(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                filename = os.path.basename(screenshot_path)
                attachment_name = f"截图_{filename}"
                if self._attach_file(msg, screenshot_path, attachment_name):
                    attached_files.append(f"截图文件: {filename}")
                    logging.info(f"已添加当前截图附件: {screenshot_path}")
                else:
                    logging.warning(f"添加当前截图附件失败: {screenshot_path}")
            
            # 记录附件信息
            if attached_files:
                logging.info(f"成功添加 {len(attached_files)} 个当前匹配文件附件: {', '.join(attached_files)}")
            else:
                logging.warning("未能添加当前匹配的文件附件，可能文件不存在或为空")
                    
        except Exception as e:
            logging.warning(f"添加当前文件附件时出错: {e}")
        
        return attached_files
    
    def _attach_log_files(self, msg, matched_keywords):
        """添加日志文件附件（保留原方法以兼容其他调用）"""
        attached_files = []
        try:
            # 添加最新的文本日志文件（基于匹配关键词）
            if os.path.exists(LOG_DIR):
                # 查找最新的相关日志文件
                log_files = []
                for filename in os.listdir(LOG_DIR):
                    if filename.endswith('.txt'):
                        # 检查文件名是否包含匹配的关键词
                        for keyword in matched_keywords:
                            if keyword in filename:
                                file_path = os.path.join(LOG_DIR, filename)
                                if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                                    log_files.append((file_path, os.path.getmtime(file_path)))
                                break
                
                # 按修改时间排序，取最新的3个文件
                log_files.sort(key=lambda x: x[1], reverse=True)
                for file_path, _ in log_files[:3]:
                    filename = os.path.basename(file_path)
                    attachment_name = f"文本日志_{filename}"
                    if self._attach_file(msg, file_path, attachment_name):
                        attached_files.append(f"文本日志: {filename}")
                        logging.info(f"已添加文本日志附件: {file_path}")
                    else:
                        logging.warning(f"跳过无效的文本日志文件: {file_path}")
            
            # 添加最新的截图文件（基于匹配关键词）
            if os.path.exists(SCREENSHOT_DIR):
                # 查找最新的相关截图文件
                image_files = []
                for filename in os.listdir(SCREENSHOT_DIR):
                    if filename.endswith(('.png', '.jpg', '.jpeg')):
                        # 检查文件名是否包含匹配的关键词
                        for keyword in matched_keywords:
                            if keyword in filename:
                                file_path = os.path.join(SCREENSHOT_DIR, filename)
                                if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                                    image_files.append((file_path, os.path.getmtime(file_path)))
                                break
                
                # 按修改时间排序，取最新的3个文件
                image_files.sort(key=lambda x: x[1], reverse=True)
                for file_path, _ in image_files[:3]:
                    filename = os.path.basename(file_path)
                    attachment_name = f"截图_{filename}"
                    if self._attach_file(msg, file_path, attachment_name):
                        attached_files.append(f"截图文件: {filename}")
                        logging.info(f"已添加截图附件: {file_path}")
                    else:
                        logging.warning(f"跳过无效的截图文件: {file_path}")
            
            # 记录附件信息
            if attached_files:
                logging.info(f"成功添加 {len(attached_files)} 个附件: {', '.join(attached_files)}")
            else:
                logging.info("未找到匹配关键词的日志或截图文件，邮件将不包含附件")
                    
        except Exception as e:
            logging.warning(f"添加日志附件时出错: {e}")
        
        return attached_files
    
    def _attach_file(self, msg, file_path, attachment_name):
        """添加单个文件附件 - 使用正确的MIME类型"""
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logging.warning(f"附件文件不存在: {file_path}")
            return False
            
        # 检查文件大小
        if os.path.getsize(file_path) == 0:
            logging.warning(f"附件文件为空: {file_path}")
            return False
            
        try:
            import mimetypes
            import re
            
            # 获取原始文件名和扩展名
            original_filename = os.path.basename(file_path)
            
            # 猜测MIME类型
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            
            # 读取文件内容
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # 简化文件名处理 - 使用ASCII安全的文件名
            import re
            import urllib.parse
            
            # 创建ASCII安全的文件名
            safe_filename = re.sub(r'[^\w\-_\.]', '_', original_filename)
            if not safe_filename or safe_filename == original_filename:
                # 如果文件名包含中文，使用时间戳作为文件名
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                ext = os.path.splitext(original_filename)[1]
                safe_filename = f"attachment_{timestamp}{ext}"
            
            # 统一使用MIMEBase处理所有附件类型
            if mime_type.startswith('text/'):
                part = MIMEBase('text', 'plain')
            elif mime_type.startswith('image/'):
                maintype, subtype = mime_type.split('/', 1)
                part = MIMEBase(maintype, subtype)
            else:
                maintype, subtype = mime_type.split('/', 1)
                part = MIMEBase(maintype, subtype)
            
            # 设置附件内容
            part.set_payload(file_data)
            encoders.encode_base64(part)
            
            # 设置附件头部 - 使用简单的filename格式
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{safe_filename}"'
            )
            
            # 添加到邮件
            msg.attach(part)
            
            logging.info(f"成功添加附件: {original_filename} (MIME类型: {mime_type})")
            return True
                    
        except Exception as e:
            logging.error(f"添加附件失败 {file_path}: {e}")
            import traceback
            logging.error(f"详细错误信息: {traceback.format_exc()}")
            return False
    
    def test_email_config(self, config=None):
        """测试邮件配置"""
        if config is None:
            config = self.get_email_config()
            
        try:
            # 获取语言配置
            lang = self._get_language_config()
            
            # 验证配置
            is_valid, msg = self.validate_config(config)
            if not is_valid:
                return False, msg
            
            # 创建测试邮件
            msg = MIMEMultipart()
            msg['From'] = config['sender_email']
            msg['To'] = config['recipient_email']
            msg['Subject'] = f"{self._get_localized_text('test_email_title', lang)} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 邮件正文
            tls_status = self._get_localized_text('enabled', lang) if config.get('use_tls', True) else self._get_localized_text('disabled', lang)
            body = f"""
            <html>
            <body>
                <h2>📧 {self._get_localized_text('test_email_title', lang)}</h2>
                <p><strong>{self._get_localized_text('test_time', lang)}:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>{self._get_localized_text('sender_email', lang)}:</strong> {config['sender_email']}</p>
                <p><strong>{self._get_localized_text('recipient_email', lang)}:</strong> {config['recipient_email']}</p>
                <p><strong>{self._get_localized_text('smtp_server', lang)}:</strong> {config['smtp_server']}:{config['smtp_port']}</p>
                <p><strong>{self._get_localized_text('tls_encryption', lang)}:</strong> {tls_status}</p>
                <hr>
                <p>{self._get_localized_text('test_success_msg', lang)}</p>
                <p><em>{self._get_localized_text('auto_sent_test', lang)}</em></p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 发送邮件 - 使用改进的连接方法
            timeout = config.get('timeout', 30)
            
            try:
                logging.info(f"尝试连接SMTP服务器: {config['smtp_server']}:{config['smtp_port']}")
                if config.get('use_ssl', False):
                    logging.info("使用SSL连接")
                    server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=timeout)
                else:
                    logging.info("使用标准SMTP连接")
                    server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=timeout)
                    if config.get('use_tls', True):
                        logging.info("启用TLS加密")
                        server.starttls()
                
                logging.info("尝试登录邮箱")
                server.login(config['sender_email'], config['sender_password'])
                logging.info("登录成功，发送邮件")
                text = msg.as_string()
                server.sendmail(config['sender_email'], config['recipient_email'], text)
                server.quit()
                logging.info("邮件发送成功")
                
            except smtplib.SMTPServerDisconnected:
                logging.warning("测试邮件: SMTP服务器断开连接，尝试重新连接...")
                time.sleep(2)
                
                if config.get('use_ssl', False):
                    server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=timeout)
                else:
                    server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=timeout)
                    if config.get('use_tls', True):
                        server.starttls()
                
                server.login(config['sender_email'], config['sender_password'])
                text = msg.as_string()
                server.sendmail(config['sender_email'], config['recipient_email'], text)
                server.quit()
            
            return True, f"测试邮件已发送到 {config['recipient_email']}，请检查邮箱"
            
        except smtplib.SMTPAuthenticationError:
            return False, "邮件认证失败，请检查邮箱账号和密码"
        except smtplib.SMTPConnectError:
            return False, "无法连接到SMTP服务器，请检查服务器地址和端口"
        except smtplib.SMTPRecipientsRefused:
            return False, "收件人地址被拒绝，请检查收件人邮箱地址"
        except smtplib.SMTPSenderRefused:
            return False, "发件人地址被拒绝，请检查发件人邮箱地址"
        except smtplib.SMTPDataError as e:
            # SMTP数据错误，但邮件可能已发送成功
            error_code = getattr(e, 'smtp_code', None)
            if error_code and str(error_code).startswith('2'):  # 2xx表示成功
                return True, f"邮件发送成功（服务器返回: {e}），请检查邮箱"
            return False, f"SMTP数据错误: {str(e)}"
        except Exception as e:
            # 检查是否是服务器响应问题但邮件已发送
            error_str = str(e)
            if 'x00' in error_str or error_str.startswith('(-1,'):
                return True, f"测试邮件已发送，请检查邮箱"
            return False, f"测试失败: {error_str}"

class EmailNotificationThread(QThread):
    """邮件通知线程"""
    
    def __init__(self, notifier, matched_keywords, ocr_text, screenshot_path=None, log_path=None):
        super().__init__()
        enhanced_logger.debug_function_call("EmailNotificationThread.__init__", {
            "matched_keywords": matched_keywords,
            "ocr_text_length": len(ocr_text) if ocr_text else 0,
            "has_screenshot": screenshot_path is not None,
            "has_log": log_path is not None
        })
        self.notifier = notifier
        self.matched_keywords = matched_keywords
        self.ocr_text = ocr_text
        self.screenshot_path = screenshot_path
        self.log_path = log_path
        logging.debug(f"邮件通知线程初始化完成，关键词: {matched_keywords}")
        
    def run(self):
        """在后台线程中发送邮件"""
        enhanced_logger.debug_function_call("EmailNotificationThread.run")
        logging.debug("邮件通知线程开始执行")
        try:
            self.notifier.send_notification(
                self.matched_keywords, 
                self.ocr_text, 
                self.screenshot_path,
                self.log_path
            )
            enhanced_logger.debug_performance("邮件通知线程执行完成")
            logging.debug("邮件通知线程执行完成")
        except Exception as e:
            enhanced_logger.debug_error("邮件通知线程执行失败", {
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            logging.error(f"邮件通知线程执行失败: {e}")