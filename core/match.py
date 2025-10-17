# core/match.py
from difflib import SequenceMatcher
import re
import logging
from core.enhanced_logger import get_enhanced_logger

# 初始化增强日志器
enhanced_logger = get_enhanced_logger()
logger = logging.getLogger('match')

def match_text(text: str, keyword: str, mode: str = "exact", fuzzy_threshold: float = 0.85) -> bool:
    """
    匹配函数：支持精确匹配、模糊匹配和正则匹配。
    """
    # 移除详细的函数调用日志以减少日志输出量
    
    if not text or not keyword:
        # 输入为空时不记录调试日志，避免大量重复输出
        return False

    result = False
    match_info = {}
    
    if mode == "exact":
        result = keyword in text
        match_info = {"mode": "exact", "keyword": keyword, "matched": result}

    elif mode == "fuzzy":
        ratio = SequenceMatcher(None, keyword, text).ratio()
        result = ratio >= fuzzy_threshold
        match_info = {"mode": "fuzzy", "keyword": keyword, "ratio": ratio, "threshold": fuzzy_threshold, "matched": result}
        # 只在匹配成功时记录模糊匹配的详细信息
        if result:
            logging.debug(f"模糊匹配成功 - 关键词: {keyword}, 相似度: {ratio:.3f}")

    elif mode == "regex":
        try:
            match_obj = re.search(keyword, text)
            result = bool(match_obj)
            match_info = {
                "mode": "regex", 
                "keyword": keyword, 
                "matched": result,
                "match_start": match_obj.start() if match_obj else None,
                "match_end": match_obj.end() if match_obj else None,
                "match_text": match_obj.group() if match_obj else None
            }
            if result:
                logging.debug(f"正则匹配成功 - 关键词: {keyword}, 匹配文本: {match_obj.group()}, 位置: {match_obj.start()}-{match_obj.end()}")
        except re.error as e:
            enhanced_logger.debug_error("match_text.regex_error", e, {
                "keyword": keyword,
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            logging.error(f"正则表达式错误: {e}")
            result = False
            match_info = {"mode": "regex", "keyword": keyword, "matched": False, "error": str(e)}
    
    else:
        enhanced_logger.debug_error(ValueError(f"未知匹配模式: {mode}"), f"match_text.unknown_mode未知匹配模式 | 上下文: {{\"mode\": \"{mode}\"}}")
        logging.warning(f"未知匹配模式: {mode}，使用精确匹配")
        result = keyword in text
        match_info = {"mode": "fallback_exact", "keyword": keyword, "matched": result}

    # 只在匹配成功时记录调试日志，避免大量失败匹配的重复日志
    if result:
        enhanced_logger.debug_performance("match_text_result", "匹配成功", match_info)
        logging.debug(f"匹配成功 - 模式: {mode}, 关键词: {keyword}")
    return result
