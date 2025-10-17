import os
import json
import csv
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Any
from PyQt6.QtCore import QObject, pyqtSignal
from core.enhanced_logger import EnhancedLogger, get_enhanced_logger

# 初始化增强日志器
enhanced_logger = EnhancedLogger("keyword_manager")

class KeywordManager(QObject):
    """关键词管理器 - 处理批量导入导出功能"""
    
    # 信号定义
    import_progress = pyqtSignal(int, str)  # 进度值, 状态消息
    export_progress = pyqtSignal(int, str)  # 进度值, 状态消息
    import_completed = pyqtSignal(bool, str, dict)  # 成功标志, 消息, 统计信息
    export_completed = pyqtSignal(bool, str)  # 成功标志, 消息
    
    def __init__(self):
        super().__init__()
        enhanced_logger.debug_function_call("KeywordManager.__init__", "初始化关键词管理器")
        enhanced_logger.debug_memory_snapshot("keyword_manager_init_start")
        logging.debug("初始化关键词管理器")
        
        self.keywords_file = "keywords.json"
        # 文本形式的关键词文件（供 KeywordPanel 使用）
        self.text_keywords_file = "target_keywords.txt"
        self.backup_dir = "keyword_backups"
        
        try:
            self.ensure_backup_dir()
            enhanced_logger.debug_memory_snapshot("KeywordManager初始化完成")
            logging.debug(f"关键词管理器初始化完成，关键词文件: {self.keywords_file}")
        except Exception as e:
            enhanced_logger.debug_error(f"KeywordManager初始化失败: {e}")
            raise
        
    def ensure_backup_dir(self):
        """确保备份目录存在"""
        enhanced_logger.debug_function_call("ensure_backup_dir")
        logging.debug(f"检查备份目录: {self.backup_dir}")
        
        try:
            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir)
                logging.debug(f"创建备份目录: {self.backup_dir}")
            else:
                logging.debug(f"备份目录已存在: {self.backup_dir}")
        except Exception as e:
            enhanced_logger.debug_error(f"创建备份目录失败: {e}")
            raise
            
    def load_keywords(self) -> List[str]:
        """加载现有关键词"""
        enhanced_logger.debug_function_call("KeywordManager.load_keywords", "加载现有关键词")
        enhanced_logger.debug_performance("load_keywords_start", "开始加载关键词")
        logging.debug(f"开始加载关键词文件: {self.keywords_file}")
        
        try:
            if os.path.exists(self.keywords_file):
                logging.debug(f"关键词文件存在，开始读取")
                with open(self.keywords_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if isinstance(data, list):
                    logging.debug(f"加载关键词列表格式，共 {len(data)} 个关键词")
                    return data
                elif isinstance(data, dict) and 'keywords' in data:
                    keywords = data['keywords']
                    logging.debug(f"加载关键词字典格式，共 {len(keywords)} 个关键词")
                    return keywords
                else:
                    logging.debug("关键词文件格式不正确，返回空列表")
                    return []
            else:
                logging.debug("关键词JSON文件不存在，尝试从文本文件加载")
                # 回退到文本文件（KeywordPanel 使用）
                try:
                    if os.path.exists(self.text_keywords_file):
                        with open(self.text_keywords_file, 'r', encoding='utf-8') as f:
                            lines = [line.strip() for line in f if line.strip()]
                        logging.debug(f"从文本文件加载关键词，共 {len(lines)} 个")
                        return lines
                    else:
                        logging.debug("文本关键词文件也不存在，返回空列表")
                        return []
                except Exception as e:
                    enhanced_logger.debug_error(f"从文本文件加载关键词失败: {e}")
                    logging.error(f"从文本文件加载关键词失败: {e}")
                    return []
        except Exception as e:
            enhanced_logger.debug_error(f"加载关键词失败: {e}")
            logging.error(f"加载关键词失败: {e}")
            return []
            
    def save_keywords(self, keywords: List[str]) -> bool:
        """保存关键词到文件"""
        enhanced_logger.debug_function_call("KeywordManager.save_keywords", {
            "keywords_count": len(keywords)
        })
        enhanced_logger.debug_performance("save_keywords_start", "开始保存关键词")
        logging.debug(f"开始保存关键词，共 {len(keywords)} 个")
        
        try:
            # 创建备份
            logging.debug("创建关键词备份")
            self.create_keywords_backup()
            
            # 保存新的关键词
            data = {
                'keywords': keywords,
                'updated_time': datetime.now().isoformat(),
                'total_count': len(keywords)
            }
            
            logging.debug(f"写入关键词JSON文件: {self.keywords_file}")
            with open(self.keywords_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 同步写入文本文件，供 KeywordPanel 直接使用显示
            try:
                logging.debug(f"同步写入文本关键词文件: {self.text_keywords_file}")
                with open(self.text_keywords_file, 'w', encoding='utf-8') as tf:
                    for kw in keywords:
                        tf.write(f"{kw}\n")
            except Exception as e:
                # 不影响主流程，但记录错误
                enhanced_logger.debug_error("写入文本关键词文件失败", e, {
                    "file_path": self.text_keywords_file
                })
                logging.error(f"写入文本关键词文件失败: {e}")
                
            enhanced_logger.debug_performance("save_keywords_success", "关键词保存成功", {
                "keywords_count": len(keywords),
                "file_path": self.keywords_file
            })
            logging.info(f"关键词已保存，共 {len(keywords)} 个")
            return True
            
        except Exception as e:
            enhanced_logger.debug_error("KeywordManager.save_keywords", e, {
                "keywords_count": len(keywords),
                "file_path": self.keywords_file,
                "error_type": type(e).__name__
            })
            logging.error(f"保存关键词失败: {e}")
            return False
            
    def create_keywords_backup(self):
        """创建关键词备份"""
        enhanced_logger.debug_function_call("create_keywords_backup")
        logging.debug("开始创建关键词备份")
        
        try:
            if os.path.exists(self.keywords_file):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = os.path.join(self.backup_dir, f"keywords_backup_{timestamp}.json")
                
                logging.debug(f"备份文件路径: {backup_file}")
                import shutil
                shutil.copy2(self.keywords_file, backup_file)
                logging.info(f"关键词备份已创建: {backup_file}")
            else:
                logging.debug("关键词文件不存在，跳过备份")
                
        except Exception as e:
            enhanced_logger.debug_error(f"创建关键词备份失败: {e}")
            logging.error(f"创建关键词备份失败: {e}")
            
    def import_from_csv(self, file_path: str, merge_mode: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        """从CSV文件导入关键词"""
        enhanced_logger.debug_function_call("import_from_csv", {
            "file_path": file_path,
            "merge_mode": merge_mode
        })
        enhanced_logger.debug_performance("import_from_csv_start", "开始CSV导入")
        logging.debug(f"开始从CSV导入关键词: {file_path}, 合并模式: {merge_mode}")
        
        try:
            self.import_progress.emit(0, "开始读取CSV文件...")
            
            imported_keywords = []
            with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
                # 尝试检测CSV格式
                sample = f.read(1024)
                f.seek(0)
                
                # 检测分隔符
                delimiter = ',' if ',' in sample else ('\t' if '\t' in sample else ';')
                
                reader = csv.reader(f, delimiter=delimiter)
                total_rows = sum(1 for _ in f)
                f.seek(0)
                
                reader = csv.reader(f, delimiter=delimiter)
                
                for i, row in enumerate(reader):
                    if i == 0:
                        # 检查是否有标题行
                        if any(header.lower() in ['keyword', 'keywords', '关键词', '关键字'] for header in row):
                            continue
                    
                    # 提取关键词（取第一列非空值）
                    for cell in row:
                        keyword = cell.strip()
                        if keyword and keyword not in imported_keywords:
                            imported_keywords.append(keyword)
                            break
                    
                    # 更新进度
                    progress = int((i + 1) / total_rows * 50)
                    self.import_progress.emit(progress, f"正在读取第 {i+1}/{total_rows} 行...")
                    
            self.import_progress.emit(60, "处理关键词数据...")
            
            # 合并或替换现有关键词
            if merge_mode:
                existing_keywords = self.load_keywords()
                original_count = len(existing_keywords)
                
                # 去重合并
                all_keywords = list(set(existing_keywords + imported_keywords))
                new_count = len(all_keywords) - original_count
            else:
                all_keywords = list(set(imported_keywords))
                new_count = len(all_keywords)
                original_count = 0
                
            self.import_progress.emit(80, "保存关键词...")
            
            # 保存关键词
            logging.debug(f"保存关键词到文件，总数: {len(all_keywords)}")
            success = self.save_keywords(all_keywords)
            
            if success:
                stats = {
                    'imported_count': len(imported_keywords),
                    'new_count': new_count,
                    'total_count': len(all_keywords),
                    'original_count': original_count,
                    'duplicates_removed': len(imported_keywords) - len(set(imported_keywords))
                }
                
                enhanced_logger.debug_performance("import_from_csv_success", "CSV导入成功", stats)
                self.import_progress.emit(100, "导入完成")
                message = f"成功导入 {stats['imported_count']} 个关键词，新增 {stats['new_count']} 个，总计 {stats['total_count']} 个"
                logging.info(f"CSV导入成功: {message}")
                return True, message, stats
            else:
                enhanced_logger.debug_error("CSV导入失败: 保存关键词失败")
                return False, "保存关键词失败", {}
                
        except Exception as e:
            error_msg = f"CSV导入失败: {e}"
            enhanced_logger.debug_error(error_msg, {"exception_type": type(e).__name__})
            logging.error(error_msg)
            return False, error_msg, {}
            
    def import_from_json(self, file_path: str, merge_mode: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        """从JSON文件导入关键词"""
        enhanced_logger.debug_function_call("import_from_json", {
            "file_path": file_path,
            "merge_mode": merge_mode
        })
        enhanced_logger.debug_performance("import_from_json_start", "开始JSON导入")
        logging.debug(f"开始从JSON导入关键词: {file_path}, 合并模式: {merge_mode}")
        
        try:
            self.import_progress.emit(0, "开始读取JSON文件...")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logging.debug(f"JSON文件读取成功，数据类型: {type(data)}")
                
            self.import_progress.emit(30, "解析JSON数据...")
            
            # 提取关键词
            imported_keywords = []
            if isinstance(data, list):
                imported_keywords = [str(item).strip() for item in data if str(item).strip()]
            elif isinstance(data, dict):
                # 尝试多种可能的键名
                possible_keys = ['keywords', 'keyword', 'words', 'items', 'data', 'list']
                for key in possible_keys:
                    if key in data:
                        if isinstance(data[key], list):
                            imported_keywords = [str(item).strip() for item in data[key] if str(item).strip()]
                            break
                        elif isinstance(data[key], str):
                            imported_keywords = [data[key].strip()]
                            break
                            
                # 如果没有找到标准键，尝试提取所有字符串值
                if not imported_keywords:
                    def extract_strings(obj):
                        strings = []
                        if isinstance(obj, str):
                            strings.append(obj.strip())
                        elif isinstance(obj, list):
                            for item in obj:
                                strings.extend(extract_strings(item))
                        elif isinstance(obj, dict):
                            for value in obj.values():
                                strings.extend(extract_strings(value))
                        return strings
                    
                    imported_keywords = extract_strings(data)
                    
            self.import_progress.emit(60, "处理关键词数据...")
            
            # 去重
            imported_keywords = list(set(keyword for keyword in imported_keywords if keyword))
            
            # 合并或替换现有关键词
            if merge_mode:
                existing_keywords = self.load_keywords()
                original_count = len(existing_keywords)
                all_keywords = list(set(existing_keywords + imported_keywords))
                new_count = len(all_keywords) - original_count
            else:
                all_keywords = imported_keywords
                new_count = len(all_keywords)
                original_count = 0
                
            self.import_progress.emit(80, "保存关键词...")
            
            # 保存关键词
            logging.debug(f"保存关键词到文件，总数: {len(all_keywords)}")
            success = self.save_keywords(all_keywords)
            
            if success:
                stats = {
                    'imported_count': len(imported_keywords),
                    'new_count': new_count,
                    'total_count': len(all_keywords),
                    'original_count': original_count
                }
                
                enhanced_logger.debug_performance("import_from_json_success", "JSON导入成功", stats)
                self.import_progress.emit(100, "导入完成")
                message = f"成功导入 {stats['imported_count']} 个关键词，新增 {stats['new_count']} 个，总计 {stats['total_count']} 个"
                logging.info(f"JSON导入成功: {message}")
                return True, message, stats
            else:
                enhanced_logger.debug_error("JSON导入失败: 保存关键词失败")
                return False, "保存关键词失败", {}
                
        except Exception as e:
            error_msg = f"JSON导入失败: {e}"
            enhanced_logger.debug_error(error_msg, {"exception_type": type(e).__name__})
            logging.error(error_msg)
            return False, error_msg, {}
            
    def import_from_txt(self, file_path: str, merge_mode: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        """从TXT文件导入关键词"""
        enhanced_logger.debug_function_call("import_from_txt", {
            "file_path": file_path,
            "merge_mode": merge_mode
        })
        enhanced_logger.debug_performance("import_from_txt_start", "开始TXT导入")
        logging.debug(f"开始从TXT导入关键词: {file_path}, 合并模式: {merge_mode}")
        
        try:
            self.import_progress.emit(0, "开始读取TXT文件...")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logging.debug(f"TXT文件读取成功，内容长度: {len(content)} 字符")
                
            self.import_progress.emit(30, "解析文本内容...")
            
            # 按行分割，支持多种分隔符
            lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
            
            imported_keywords = []
            for line in lines:
                # 支持多种分隔符：逗号、分号、制表符、空格
                if ',' in line:
                    keywords = line.split(',')
                elif ';' in line:
                    keywords = line.split(';')
                elif '\t' in line:
                    keywords = line.split('\t')
                else:
                    keywords = [line]
                    
                for keyword in keywords:
                    keyword = keyword.strip()
                    if keyword and keyword not in imported_keywords:
                        imported_keywords.append(keyword)
                        
            self.import_progress.emit(60, "处理关键词数据...")
            
            # 合并或替换现有关键词
            if merge_mode:
                existing_keywords = self.load_keywords()
                original_count = len(existing_keywords)
                all_keywords = list(set(existing_keywords + imported_keywords))
                new_count = len(all_keywords) - original_count
            else:
                all_keywords = list(set(imported_keywords))
                new_count = len(all_keywords)
                original_count = 0
                
            self.import_progress.emit(80, "保存关键词...")
            
            # 保存关键词
            logging.debug(f"保存关键词到文件，总数: {len(all_keywords)}")
            success = self.save_keywords(all_keywords)
            
            if success:
                stats = {
                    'imported_count': len(imported_keywords),
                    'new_count': new_count,
                    'total_count': len(all_keywords),
                    'original_count': original_count,
                    'duplicates_removed': len(imported_keywords) - len(set(imported_keywords))
                }
                
                enhanced_logger.debug_performance("import_from_txt_success", "TXT导入成功", stats)
                self.import_progress.emit(100, "导入完成")
                message = f"成功导入 {stats['imported_count']} 个关键词，新增 {stats['new_count']} 个，总计 {stats['total_count']} 个"
                logging.info(f"TXT导入成功: {message}")
                return True, message, stats
            else:
                enhanced_logger.debug_error("TXT导入失败: 保存关键词失败")
                return False, "保存关键词失败", {}
                
        except Exception as e:
            error_msg = f"TXT导入失败: {e}"
            enhanced_logger.debug_error(error_msg, {"exception_type": type(e).__name__})
            logging.error(error_msg)
            return False, error_msg, {}
            
    def export_to_csv(self, file_path: str, include_metadata: bool = True) -> Tuple[bool, str]:
        """导出关键词到CSV文件"""
        enhanced_logger.debug_function_call("export_to_csv", {
            "file_path": file_path,
            "include_metadata": include_metadata
        })
        enhanced_logger.debug_performance("export_to_csv_start", "开始CSV导出")
        logging.debug(f"开始导出关键词到CSV: {file_path}, 包含元数据: {include_metadata}")
        
        try:
            self.export_progress.emit(0, "开始导出到CSV...")
            
            keywords = self.load_keywords()
            if not keywords:
                enhanced_logger.debug_error("导出失败: 没有关键词可导出")
                return False, "没有关键词可导出"
                
            self.export_progress.emit(30, "准备CSV数据...")
            
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                
                # 写入标题行
                if include_metadata:
                    writer.writerow(['关键词', '序号', '导出时间'])
                    export_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    for i, keyword in enumerate(keywords, 1):
                        writer.writerow([keyword, i, export_time])
                        
                        # 更新进度
                        progress = 30 + int((i / len(keywords)) * 60)
                        self.export_progress.emit(progress, f"正在写入第 {i}/{len(keywords)} 个关键词...")
                else:
                    writer.writerow(['关键词'])
                    
                    for i, keyword in enumerate(keywords, 1):
                        writer.writerow([keyword])
                        
                        # 更新进度
                        progress = 30 + int((i / len(keywords)) * 60)
                        self.export_progress.emit(progress, f"正在写入第 {i}/{len(keywords)} 个关键词...")
                        
            enhanced_logger.debug_performance("export_to_csv_success", "CSV导出成功", {
                "keywords_count": len(keywords),
                "file_path": file_path
            })
            self.export_progress.emit(100, "导出完成")
            message = f"成功导出 {len(keywords)} 个关键词到 {file_path}"
            logging.info(message)
            return True, message
            
        except Exception as e:
            error_msg = f"CSV导出失败: {e}"
            enhanced_logger.debug_error(error_msg, {"exception_type": type(e).__name__})
            logging.error(error_msg)
            return False, error_msg
            
    def export_to_json(self, file_path: str, include_metadata: bool = True) -> Tuple[bool, str]:
        """导出关键词到JSON文件"""
        enhanced_logger.debug_function_call("export_to_json", {
            "file_path": file_path,
            "include_metadata": include_metadata
        })
        enhanced_logger.debug_performance("export_to_json_start", "开始JSON导出")
        logging.debug(f"开始导出关键词到JSON: {file_path}, 包含元数据: {include_metadata}")
        
        try:
            self.export_progress.emit(0, "开始导出到JSON...")
            
            keywords = self.load_keywords()
            if not keywords:
                enhanced_logger.debug_error("导出失败: 没有关键词可导出")
                return False, "没有关键词可导出"
                
            self.export_progress.emit(30, "准备JSON数据...")
            
            if include_metadata:
                data = {
                    'keywords': keywords,
                    'metadata': {
                        'total_count': len(keywords),
                        'export_time': datetime.now().isoformat(),
                        'export_format': 'json',
                        'version': '1.0'
                    }
                }
            else:
                data = keywords
                
            self.export_progress.emit(70, "写入JSON文件...")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            enhanced_logger.debug_performance("export_to_json_success", "JSON导出成功", {
                "keywords_count": len(keywords),
                "file_path": file_path
            })
            self.export_progress.emit(100, "导出完成")
            message = f"成功导出 {len(keywords)} 个关键词到 {file_path}"
            logging.info(message)
            return True, message
            
        except Exception as e:
            error_msg = f"JSON导出失败: {e}"
            enhanced_logger.debug_error(error_msg, {"exception_type": type(e).__name__})
            logging.error(error_msg)
            return False, error_msg
            
    def export_to_txt(self, file_path: str, separator: str = '\n') -> Tuple[bool, str]:
        """导出关键词到TXT文件"""
        enhanced_logger.debug_function_call("export_to_txt", {
            "file_path": file_path,
            "separator": repr(separator)
        })
        enhanced_logger.debug_performance("export_to_txt_start", "开始TXT导出")
        logging.debug(f"开始导出关键词到TXT: {file_path}, 分隔符: {repr(separator)}")
        
        try:
            self.export_progress.emit(0, "开始导出到TXT...")
            
            keywords = self.load_keywords()
            if not keywords:
                enhanced_logger.debug_error("导出失败: 没有关键词可导出")
                return False, "没有关键词可导出"
                
            self.export_progress.emit(30, "准备文本数据...")
            
            # 根据分隔符类型处理
            if separator == '\n':
                content = '\n'.join(keywords)
            elif separator == ',':
                content = ', '.join(keywords)
            elif separator == ';':
                content = '; '.join(keywords)
            elif separator == '\t':
                content = '\t'.join(keywords)
            else:
                content = separator.join(keywords)
                
            self.export_progress.emit(70, "写入TXT文件...")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            enhanced_logger.debug_performance("export_to_txt_success", "TXT导出成功", {
                "keywords_count": len(keywords),
                "file_path": file_path
            })
            self.export_progress.emit(100, "导出完成")
            message = f"成功导出 {len(keywords)} 个关键词到 {file_path}"
            logging.info(message)
            return True, message
            
        except Exception as e:
            error_msg = f"TXT导出失败: {e}"
            enhanced_logger.debug_error(error_msg, {"exception_type": type(e).__name__})
            logging.error(error_msg)
            return False, error_msg
            
    def get_import_stats(self) -> Dict[str, Any]:
        """获取导入统计信息"""
        enhanced_logger.debug_function_call("get_import_stats")
        enhanced_logger.debug_performance("get_import_stats_start", "开始获取统计信息")
        logging.debug("开始获取导入统计信息")
        
        try:
            keywords = self.load_keywords()
            logging.debug(f"加载关键词完成，共 {len(keywords)} 个")
            
            # 统计关键词长度分布
            length_stats = {}
            for keyword in keywords:
                length = len(keyword)
                length_stats[length] = length_stats.get(length, 0) + 1
                
            # 统计字符类型
            chinese_count = 0
            english_count = 0
            number_count = 0
            mixed_count = 0
            
            for keyword in keywords:
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in keyword)
                has_english = any(char.isalpha() and ord(char) < 128 for char in keyword)
                has_number = any(char.isdigit() for char in keyword)
                
                if has_chinese and has_english:
                    mixed_count += 1
                elif has_chinese:
                    chinese_count += 1
                elif has_english:
                    english_count += 1
                elif has_number:
                    number_count += 1
                    
            return {
                'total_keywords': len(keywords),
                'length_distribution': length_stats,
                'type_distribution': {
                    'chinese': chinese_count,
                    'english': english_count,
                    'number': number_count,
                    'mixed': mixed_count
                },
                'average_length': sum(len(k) for k in keywords) / len(keywords) if keywords else 0,
                'longest_keyword': max(keywords, key=len) if keywords else '',
                'shortest_keyword': min(keywords, key=len) if keywords else ''
            }
            
        except Exception as e:
            enhanced_logger.debug_error(f"获取导入统计失败: {e}")
            logging.error(f"获取导入统计失败: {e}")
            return {}
            
    def validate_keywords(self, keywords: List[str]) -> Tuple[List[str], List[str]]:
        """验证关键词有效性"""
        enhanced_logger.debug_function_call("KeywordManager.validate_keywords", {
            "keywords_count": len(keywords)
        })
        enhanced_logger.debug_performance("validate_keywords_start", "开始验证关键词")
        logging.debug(f"开始验证关键词有效性，共 {len(keywords)} 个关键词")
        
        valid_keywords = []
        invalid_keywords = []
        validation_stats = {
            "empty_count": 0,
            "too_long_count": 0,
            "special_char_count": 0
        }
        
        for keyword in keywords:
            keyword = keyword.strip()
            
            # 检查是否为空
            if not keyword:
                invalid_keywords.append("(空关键词)")
                validation_stats["empty_count"] += 1
                continue
                
            # 检查长度
            if len(keyword) > 100:
                invalid_keywords.append(f"{keyword[:20]}...(过长)")
                validation_stats["too_long_count"] += 1
                continue
                
            # 检查特殊字符
            if any(char in keyword for char in ['\n', '\r', '\t']):
                invalid_keywords.append(f"{keyword}(包含换行符)")
                validation_stats["special_char_count"] += 1
                continue
                
            valid_keywords.append(keyword)
            
        enhanced_logger.debug_performance("validate_keywords_complete", "关键词验证完成", {
            "valid_count": len(valid_keywords),
            "invalid_count": len(invalid_keywords),
            **validation_stats
        })
        logging.debug(f"关键词验证完成，有效: {len(valid_keywords)} 个，无效: {len(invalid_keywords)} 个")
        return valid_keywords, invalid_keywords