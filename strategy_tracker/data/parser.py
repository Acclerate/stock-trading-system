"""
输出文件解析器
解析不同策略生成的输出文件
"""
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod

from ..config import OUTPUTS_DIR, STRATEGY_TYPES, DATE_FORMAT


class BaseParser(ABC):
    """解析器基类"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = None
        self.lines = None

    def read_file(self) -> bool:
        """读取文件内容"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
                self.lines = self.content.split('\n')
            return True
        except Exception as e:
            print(f"读取文件失败 {self.file_path}: {e}")
            return False

    @abstractmethod
    def parse(self) -> Optional[Dict[str, Any]]:
        """解析文件，返回标准化结果"""
        pass

    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%Y%m%d',
            '%Y.%m.%d',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def extract_timestamp(filename: str) -> Optional[datetime]:
        """从文件名提取时间戳"""
        # 格式: strategy_name_YYYYMMDD_HHMMSS.txt
        match = re.search(r'(\d{8})_(\d{6})', filename)
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            try:
                return datetime.strptime(f"{date_str}{time_str}", '%Y%m%d%H%M%S')
            except ValueError:
                pass
        return None

    @staticmethod
    def clean_stock_code(code: str) -> str:
        """清理股票代码，去除市场后缀"""
        code = code.strip()
        # 移除 .SH, .SZ, .SHSE, .SZSE 等后缀
        code = re.sub(r'\.(SH|SZ|SHSE|SZSE)$', '', code, flags=re.IGNORECASE)
        return code


class TrendStocksParser(BaseParser):
    """趋势股筛选结果解析器"""

    def parse(self) -> Optional[Dict[str, Any]]:
        """解析趋势股筛选文件"""
        if not self.read_file():
            return None

        result = {
            'strategy_type': 'trend_stocks',
            'screen_date': None,
            'generated_at': None,
            'total_stocks': 0,
            'strategy_params': None,
            'stocks': []
        }

        # 提取生成时间
        for line in self.lines:
            if '生成时间:' in line:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                if date_match:
                    result['generated_at'] = self.parse_date(date_match.group(1))
                    result['screen_date'] = result['generated_at']
                break

        # 提取符合数量
        for line in self.lines:
            if '符合数量:' in line:
                match = re.search(r'符合数量:\s*(\d+)', line)
                if match:
                    result['total_stocks'] = int(match.group(1))
                break

        # 解析股票列表
        in_stock_section = False
        header_pattern = re.compile(
            r'序号\s+名称\s+代码\s+日期\s+股价\s+MA5\s+MA10\s+MA30'
        )

        for line in self.lines:
            # 检测是否进入股票列表区域
            if '=== 趋势股列表' in line or '=== 股票列表' in line:
                in_stock_section = True
                continue

            if in_stock_section and line.strip().startswith('==='):
                break

            if in_stock_section and line.strip() and not line.startswith('-'):
                # 解析股票行
                # 格式: 1     洲际油气      600759    2026-03-05    8.70    7.50...
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        idx = int(parts[0])
                        name = parts[1]
                        code = self.clean_stock_code(parts[2])
                        date_str = parts[3]
                        price = float(parts[4]) if len(parts) > 4 else None
                        ma5 = float(parts[5]) if len(parts) > 5 else None
                        ma10 = float(parts[6]) if len(parts) > 6 else None
                        ma30 = float(parts[7]) if len(parts) > 7 else None
                        ma5_pct = parts[8] if len(parts) > 8 else None
                        spread_pct = parts[9] if len(parts) > 9 else None
                        return_pct = parts[10] if len(parts) > 10 else None
                        vol_ratio = parts[11] if len(parts) > 11 else None
                        score = float(parts[-1]) if len(parts) > 12 else None

                        stock_info = {
                            'stock_code': code,
                            'stock_name': name,
                            'screen_date': result['screen_date'],
                            'screen_price': price,
                            'score': score,
                            'reason': f"MA5:{ma5} MA10:{ma10} MA30:{ma30}"
                        }
                        result['stocks'].append(stock_info)
                    except (ValueError, IndexError):
                        continue

        return result if result['stocks'] else None


class HS300ScreenParser(BaseParser):
    """沪深300筛选结果解析器"""

    def parse(self) -> Optional[Dict[str, Any]]:
        """解析沪深300筛选文件"""
        if not self.read_file():
            return None

        result = {
            'strategy_type': 'hs300_screen',
            'screen_date': None,
            'generated_at': None,
            'total_stocks': 0,
            'strategy_params': None,
            'stocks': []
        }

        # 提取生成时间和回测区间
        for line in self.lines:
            if '生成时间:' in line:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                if date_match:
                    result['generated_at'] = self.parse_date(date_match.group(1))

            if '符合数量:' in line:
                match = re.search(r'符合数量:\s*(\d+)', line)
                if match:
                    result['total_stocks'] = int(match.group(1))

            if '回测区间:' in line:
                # 提取结束日期作为筛选日期
                date_match = re.search(r'(\d{8})\s*~', line)
                if date_match:
                    result['screen_date'] = datetime.strptime(date_match.group(1), '%Y%m%d')

        # 如果没有找到screen_date，使用generated_at
        if result['screen_date'] is None and result['generated_at']:
            result['screen_date'] = result['generated_at']

        # 解析股票列表
        in_stock_section = False
        for i, line in enumerate(self.lines):
            if '=== 买入信号股票推荐' in line:
                in_stock_section = True
                # 跳过表头和分隔线
                continue

            if in_stock_section:
                if line.startswith('=') or line.startswith('【') or '买入条件说明' in line:
                    break

                # 跳过表头行和分隔线
                if any(keyword in line for keyword in ['名称', '代码', '最新日期', '-----', '====']):
                    continue

                # 解析股票行
                # 格式: 中航沈飞                600760.SH      2026-03-05   55.95 169.45%  均线金叉 + MACD金叉
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        name = parts[0]
                        code = self.clean_stock_code(parts[1])
                        date_str = parts[2]
                        price = None
                        return_rate = None
                        reason = None

                        # 尝试解析价格
                        for j, part in enumerate(parts[2:], 2):
                            try:
                                price = float(part)
                                break
                            except ValueError:
                                continue

                        # 尝试解析收益率
                        for part in parts:
                            if '%' in part:
                                try:
                                    return_rate = float(part.replace('%', ''))
                                    break
                                except ValueError:
                                    continue

                        # 提取原因（最后一部分）
                        if '判定依据' in line:
                            reason_idx = line.index('判定依据')
                            reason = line[reason_idx + 5:].strip()
                        else:
                            reason = ' '.join(parts[-2:])

                        stock_info = {
                            'stock_code': code,
                            'stock_name': name,
                            'screen_date': result['screen_date'],
                            'screen_price': price,
                            'score': return_rate,
                            'reason': reason
                        }
                        result['stocks'].append(stock_info)
                    except (ValueError, IndexError):
                        continue

        return result if result['stocks'] else None


class LowVolumeBreakoutParser(BaseParser):
    """低位放量突破策略解析器"""

    def parse(self) -> Optional[Dict[str, Any]]:
        """解析低位放量突破筛选文件"""
        if not self.read_file():
            return None

        result = {
            'strategy_type': 'low_volume_breakout',
            'screen_date': None,
            'generated_at': None,
            'total_stocks': 0,
            'strategy_params': None,
            'stocks': []
        }

        # 提取生成时间
        for line in self.lines:
            if '生成时间' in line or '时间' in line:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                if date_match:
                    result['generated_at'] = self.parse_date(date_match.group(1))
                    result['screen_date'] = result['generated_at']
                break

        # 检测文件格式并解析
        # 低位放量突破可能有不同的格式，这里做一个通用解析

        in_stock_section = False

        for line in self.lines:
            # 检测股票列表开始
            if any(keyword in line for keyword in ['股票列表', '筛选结果', '推荐股票']):
                in_stock_section = True
                continue

            if in_stock_section and line.strip().startswith('==='):
                break

            # 解析股票行
            if in_stock_section and line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    # 尝试识别股票代码（6位数字）
                    for part in parts:
                        code_match = re.match(r'(\d{6})', part)
                        if code_match:
                            code = code_match.group(1)

                            # 尝试提取名称（通常在代码前面）
                            code_idx = parts.index(part)
                            name = parts[code_idx - 1] if code_idx > 0 else ''

                            # 尝试提取价格
                            price = None
                            for p in parts[code_idx:]:
                                try:
                                    price = float(p)
                                    break
                                except ValueError:
                                    continue

                            stock_info = {
                                'stock_code': code,
                                'stock_name': name,
                                'screen_date': result['screen_date'],
                                'screen_price': price,
                                'score': None,
                                'reason': '低位放量突破'
                            }
                            result['stocks'].append(stock_info)
                            break

        return result if result['stocks'] else None


class UniversalParser(BaseParser):
    """通用解析器 - 自动识别文件类型"""

    def parse(self) -> Optional[Dict[str, Any]]:
        """自动识别并解析文件"""
        if not self.read_file():
            return None

        content = self.content.lower()

        # 根据文件内容特征选择解析器
        if '趋势股' in content or 'trend' in self.file_path.name.lower():
            parser = TrendStocksParser(self.file_path)
        elif '沪深300' in content or 'hs300' in self.file_path.name.lower():
            parser = HS300ScreenParser(self.file_path)
        elif '低位放量' in content or 'low_volume' in self.file_path.name.lower():
            parser = LowVolumeBreakoutParser(self.file_path)
        elif '中证500' in content or 'zz500' in self.file_path.name.lower():
            # 使用类似HS300的解析器
            parser = HS300ScreenParser(self.file_path)
            if parser.parse():
                result = parser.parse()
                if result:
                    result['strategy_type'] = 'zz500_screen'
                    return result
        elif '中证1000' in content or 'zz1000' in self.file_path.name.lower():
            parser = HS300ScreenParser(self.file_path)
            if parser.parse():
                result = parser.parse()
                if result:
                    result['strategy_type'] = 'zz1000_screen'
                    return result
        else:
            # 默认使用HS300格式
            parser = HS300ScreenParser(self.file_path)

        return parser.parse()


def parse_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """解析单个文件"""
    parser = UniversalParser(file_path)
    return parser.parse()


def parse_directory(directory: Path = None) -> List[Dict[str, Any]]:
    """解析目录下所有输出文件"""
    if directory is None:
        directory = OUTPUTS_DIR

    results = []

    # 递归查找所有txt文件
    for file_path in directory.rglob('*.txt'):
        # 跳过非策略输出文件
        if any(pattern in str(file_path) for pattern in ['__pycache__', '.git', 'test']):
            continue

        result = parse_file(file_path)
        if result and result.get('stocks'):
            result['file_path'] = str(file_path)
            results.append(result)

    return results


def get_strategy_from_filename(filename: str) -> Optional[str]:
    """从文件名推断策略类型"""
    filename_lower = filename.lower()

    if 'trend_stocks' in filename_lower or 'trendstocks' in filename_lower:
        return 'trend_stocks'
    elif 'hs300' in filename_lower or '沪深300' in filename:
        return 'hs300_screen'
    elif 'zz500' in filename_lower or '中证500' in filename:
        return 'zz500_screen'
    elif 'zz1000' in filename_lower or '中证1000' in filename:
        return 'zz1000_screen'
    elif 'low_volume' in filename_lower or '低位放量' in filename:
        return 'low_volume_breakout'
    elif 'stock_screen' in filename_lower:
        return 'stock_screen'

    return None
