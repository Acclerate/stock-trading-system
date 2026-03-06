"""
趋势股筛选系统
筛选条件：
1. 5日、10日、30日均线均往上
2. 非创业板、非科创板、非ST股票
3. 股票范围：全A股（主板+中小板）

参考 quick_select.py，优先从缓存读取数据
"""
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_resilient import DataResilient
from data.cache_manager import CacheManager


# ========== 股票过滤配置 ==========
def normalize_symbol(symbol):
    """
    标准化股票代码格式
    SHSE.600519 -> 600519
    SZSE.000001 -> 000001
    600519 -> 600519
    """
    if '.' in str(symbol):
        return symbol.split('.')[-1]
    return symbol


def get_all_a_stocks():
    """
    使用掘金SDK获取全A股列表，并过滤掉：
    - 创业板（30xxxx）
    - 科创板（688xxx）
    - ST股票
    """
    cache_key = 'all_a_stocks_filtered'

    # 尝试从缓存加载
    cached = CacheManager.load_macro_cache(cache_key)
    if cached is not None:
        # 标准化所有代码（兼容旧缓存格式）
        normalized = [normalize_symbol(s) for s in cached]
        print(f"✅ 从缓存加载 {len(normalized)} 只股票")
        return normalized

    try:
        # 检查掘金SDK是否可用
        try:
            from gm.api import get_instruments
        except ImportError:
            raise ValueError("掘金SDK未安装，请先安装: pip install gm-python-sdk")

        print("正在使用掘金SDK获取全A股列表...")

        # 获取所有股票（sec_types=1 表示股票）
        df = get_instruments(sec_types=1, df=True)

        if df is None or df.empty:
            raise ValueError("掘金SDK返回空数据")

        # 确保列名存在
        if 'symbol' not in df.columns:
            raise ValueError("掘金SDK返回数据缺少symbol列")

        # 提取股票代码（从 SHSE.600519 格式转换为 600519）
        df['code'] = df['symbol'].apply(lambda x: x.split('.')[-1] if '.' in str(x) else str(x))

        # 获取股票名称（如果有sec_name列）
        if 'sec_name' in df.columns:
            df['name'] = df['sec_name']
        else:
            df['name'] = ''

        # 过滤条件
        # 1. 过滤创业板（300xxx）和科创板（688xxx）
        df = df[~df['code'].str.startswith('300')]
        df = df[~df['code'].str.startswith('688')]
        df = df[~df['code'].str.startswith('301')]  # 创业板注册制

        # 2. 过滤ST股票（名称包含ST、*ST、S*ST等）
        df = df[~df['name'].str.contains('ST|退|暂停', na=False)]

        # 3. 只保留主板和中小板
        # 上海主板：600xxx, 601xxx, 603xxx, 605xxx
        # 深圳主板：000xxx, 001xxx
        # 中小板：002xxx
        valid_prefixes = ['600', '601', '603', '605', '000', '001', '002']
        df = df[df['code'].str[:3].isin(valid_prefixes)]

        # 返回纯代码列表（不带市场后缀，用于缓存文件匹配）
        codes = df['code'].tolist()

        # 保存代码-名称映射
        code_name_dict = dict(zip(df['code'], df['name']))
        CacheManager.save_macro_cache('stock_name_dict', code_name_dict)

        print(f"✅ 获取到 {len(codes)} 只股票（已过滤创业板、科创板、ST股）")

        # 保存缓存
        CacheManager.save_macro_cache(cache_key, codes)

        return codes

    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []


def get_stock_name_map():
    """获取股票代码-名称映射"""
    cache_key = 'stock_name_dict'
    cached = CacheManager.load_macro_cache(cache_key)
    if cached is not None:
        return cached
    return {}


def load_stock_from_cache(symbol):
    """
    从缓存加载股票数据
    参考 quick_select.py 的实现方式
    """
    cache_dir = Path("cache/stock")

    # 标准化代码（纯数字，用于缓存文件匹配）
    code = normalize_symbol(symbol)

    # 查找该股票的所有缓存文件
    stock_files = []

    for cache_file in cache_dir.glob(f"{code}_*.pkl"):
        try:
            parts = cache_file.stem.split('_')
            if len(parts) >= 3:
                start_date = parts[1]
                end_date = parts[2]
                stock_files.append((cache_file, start_date, end_date))
        except Exception:
            continue

    if not stock_files:
        return None

    # 按结束日期排序，取最新的
    stock_files.sort(key=lambda x: x[2], reverse=True)
    latest_file, start_date, end_date = stock_files[0]

    try:
        with open(latest_file, 'rb') as f:
            df = pickle.load(f)
        return df
    except Exception:
        return None


def fetch_stock_data_with_fallback(symbol, start_date, end_date):
    """
    获取股票数据，优先从缓存读取，缓存不存在时使用 DataResilient
    """
    # 1. 先尝试从缓存读取
    df = load_stock_from_cache(symbol)
    if df is not None and not df.empty:
        return df

    # 2. 缓存不存在，使用 DataResilient 获取（需要纯代码）
    code = normalize_symbol(symbol)
    try:
        df = DataResilient.fetch_stock_data(code, start_date, end_date, use_cache=True)
        return df
    except Exception:
        return None


# ========== 指标计算模块 ==========
def calculate_trend_indicators(df):
    """
    计算趋势指标：
    - 均线：5日、10日、30日
    - 成交量：5日、10日、20日均量，量比
    """
    # 计算均线
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    df['ma30'] = df['close'].rolling(window=30).mean()

    # 计算成交量均线
    df['vol_ma5'] = df['volume'].rolling(window=5).mean()
    df['vol_ma10'] = df['volume'].rolling(window=10).mean()
    df['vol_ma20'] = df['volume'].rolling(window=20).mean()

    # 计算量比（当日成交量 / 5日均量）
    df['vol_ratio'] = df['volume'] / df['vol_ma5']

    # 计算成交量变化率
    df['volume_pct_change'] = df['volume'].pct_change()

    return df


# ========== 趋势判断模块 ==========
def check_trend_stock(df):
    """
    判断是否为趋势股

    条件：
    1. MA5 > MA10 > MA30（多头排列）
    2. 三条均线均向上延伸

    返回：{
        'is_trend': bool,
        'trend_score': float,  # 趋势强度评分
        'details': dict
    }
    """
    if df is None or len(df) < 35:
        return {'is_trend': False, 'trend_score': 0, 'details': {'reason': '数据不足'}}

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # 获取最新均线值
    ma5 = latest['ma5']
    ma10 = latest['ma10']
    ma30 = latest['ma30']

    # 检查多头排列
    ma_order_ok = (ma5 > ma10) and (ma10 > ma30)

    if not ma_order_ok or pd.isna(ma5) or pd.isna(ma10) or pd.isna(ma30):
        return {
            'is_trend': False,
            'trend_score': 0,
            'details': {'reason': '非多头排列或数据不全'}
        }

    # 检查三条均线是否都在上升（当天 > 前一天）
    ma5_rising = latest['ma5'] > prev['ma5']
    ma10_rising = latest['ma10'] > prev['ma10']
    ma30_rising = latest['ma30'] > prev['ma30']

    all_rising = ma5_rising and ma10_rising and ma30_rising

    if not all_rising:
        return {
            'is_trend': False,
            'trend_score': 0,
            'details': {
                'reason': '均线未全部上升',
                'ma5_rising': ma5_rising,
                'ma10_rising': ma10_rising,
                'ma30_rising': ma30_rising
            }
        }

    # 成交量分析
    volume = latest['volume']
    vol_ma5 = latest['vol_ma5']
    vol_ma10 = latest['vol_ma10']
    vol_ratio = latest['vol_ratio'] if pd.notna(latest['vol_ratio']) else 1.0

    # 放量判断
    # 轻度放量：量比 > 1.2
    # 明显放量：量比 > 1.5
    # 巨量：量比 > 2.0
    if vol_ratio >= 2.0:
        volume_level = "巨量"
    elif vol_ratio >= 1.5:
        volume_level = "明显放量"
    elif vol_ratio >= 1.2:
        volume_level = "轻度放量"
    else:
        volume_level = "缩量/平量"

    # 计算趋势强度评分
    price = latest['close']
    ma5_gap = (price - ma5) / ma5 if ma5 > 0 else 0  # 股价在MA5上方的距离
    ma_spread = (ma5 - ma30) / ma30 if ma30 > 0 else 0  # MA5与MA30的间距

    # 计算近期涨幅（5日）
    recent_return = (price - df.iloc[-5]['close']) / df.iloc[-5]['close'] if len(df) >= 5 else 0

    # 成交量得分（0-15分）
    # 量比越大，得分越高
    volume_score = 0
    if vol_ratio >= 2.0:
        volume_score = 15  # 巨量
    elif vol_ratio >= 1.5:
        volume_score = 12  # 明显放量
    elif vol_ratio >= 1.2:
        volume_score = 8   # 轻度放量
    elif vol_ratio >= 1.0:
        volume_score = 5   # 正常
    else:
        volume_score = 2   # 缩量

    # 趋势强度评分（0-115）
    trend_score = (
        min(max(ma_spread * 400, 0), 35) +  # 均线间距得分
        min(max(ma5_gap * 180, 0), 25) +    # 股价位置得分
        min(max(recent_return * 250, 0), 25) + # 近期涨幅得分
        volume_score                       # 成交量得分
    )

    return {
        'is_trend': True,
        'trend_score': round(trend_score, 2),
        'details': {
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma30': round(ma30, 2),
            'price': round(price, 2),
            'ma5_gap': round(ma5_gap * 100, 2),
            'ma_spread': round(ma_spread * 100, 2),
            'recent_return': round(recent_return * 100, 2),
            # 成交量数据
            'volume': int(volume) if pd.notna(volume) else 0,
            'vol_ma5': int(vol_ma5) if pd.notna(vol_ma5) else 0,
            'vol_ma10': int(vol_ma10) if pd.notna(vol_ma10) else 0,
            'vol_ratio': round(vol_ratio, 2),
            'volume_level': volume_level,
            'volume_score': volume_score
        }
    }


# ========== 处理单只股票 ==========
def process_single_stock(symbol, name_map, start_date, end_date):
    """处理单只股票"""
    stock_name = name_map.get(symbol, "")

    try:
        df = fetch_stock_data_with_fallback(symbol, start_date, end_date)
        if df is None or df.empty:
            return None

        df = calculate_trend_indicators(df)
        result = check_trend_stock(df)

        if result['is_trend']:
            return {
                'symbol': symbol,
                'name': stock_name,
                'trend_score': result['trend_score'],
                'details': result['details'],
                'latest_date': df.index[-1].strftime('%Y-%m-%d')
            }
        return None

    except Exception:
        return None


# ========== 主程序 ==========
def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description='趋势股筛选系统 - 基于均线多头排列筛选趋势股',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
筛选条件:
  1. MA5 > MA10 > MA30（多头排列）
  2. 三条均线均向上
  3. 非创业板、非科创板、非ST股票

示例:
  python trend_stocks.py              # 使用默认参数
  python trend_stocks.py -t 60        # 设置回测天数为60天
  python trend_stocks.py -r           # 刷新股票列表缓存
        '''
    )
    parser.add_argument('-d', '--days', type=int, default=90,
                        help='回测天数 (默认: 90)')
    parser.add_argument('-r', '--refresh', action='store_true',
                        help='刷新股票列表缓存')

    args = parser.parse_args()

    # 初始化缓存管理器
    CacheManager.initialize()

    # 如果需要刷新缓存，先删除
    if args.refresh:
        print("正在刷新股票列表缓存...")
        CacheManager.clear_macro_cache('all_a_stocks_filtered')
        CacheManager.clear_macro_cache('stock_name_dict')

    print("=" * 60)
    print("趋势股筛选系统")
    print("=" * 60)
    print(f"回测天数: {args.days}天")
    print("=" * 60)
    print()

    # 获取全A股列表
    symbols = get_all_a_stocks()
    if not symbols:
        raise ValueError("无法获取股票列表")

    # 获取股票名称映射
    name_map = get_stock_name_map()
    print(f"✅ 获取到 {len(name_map)} 只股票名称")
    print()

    # 日期设置
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")

    # 串行处理股票（避免过多并发请求）
    results = []
    failed_count = 0
    total = len(symbols)

    print(f"开始分析 {total} 只股票...")
    print()

    for idx, symbol in enumerate(symbols, 1):
        # 进度显示
        if idx % 50 == 0 or idx == total:
            print(f"进度: {idx}/{total} ({idx/total*100:.1f}%) - 找到趋势股: {len(results)} 只")

        result = process_single_stock(symbol, name_map, start_date, end_date)
        if result:
            results.append(result)
        else:
            failed_count += 1

    # 按趋势强度评分排序
    sorted_results = sorted(results, key=lambda x: x['trend_score'], reverse=True)

    # ========== 使用统一输出工具 ==========
    from utils.strategy_output import StrategyOutputManager, StrategyMetadata, StockData
    from strategy_tracker.db.repository import get_repository

    # 创建策略元数据
    metadata = StrategyMetadata(
        strategy_name="趋势股筛选",
        strategy_type="trend_stocks",
        screen_date=datetime.now(),
        generated_at=datetime.now(),
        scan_count=total,
        match_count=len(sorted_results),
        strategy_params={
            'backtest_days': args.days,
            'refresh_cache': args.refresh
        },
        filter_conditions="MA5 > MA10 > MA30 且 三条均线均向上",
        scan_scope="全A股（剔除创业板、科创板、ST股）"
    )

    # 创建输出管理器
    output_mgr = StrategyOutputManager(metadata)

    # 添加股票数据
    for item in sorted_results:
        d = item['details']
        stock_code = item['symbol']  # 已经是纯代码格式

        stock = StockData(
            stock_code=stock_code,
            stock_name=item['name'],
            screen_price=d['price'],
            score=item['trend_score'],
            reason=f"趋势股 (量级:{d['volume_level']})",
            extra_fields={
                'ma5': d['ma5'],
                'ma10': d['ma10'],
                'ma30': d['ma30'],
                'ma5_gap': d['ma5_gap'],
                'ma_spread': d['ma_spread'],
                'recent_return': d['recent_return'],
                'vol_ratio': d['vol_ratio'],
                'volume_level': d['volume_level'],
                'latest_date': item['latest_date']
            }
        )
        output_mgr.add_stock(stock)

    # 自定义表格格式化函数（保持原有格式）
    def format_trend_table(stocks):
        rows = []
        if stocks:
            rows.append("=== 趋势股列表 (按趋势强度评分降序) ===")
            rows.append(
                f"{'序号':<6}{'名称':<16}{'代码':<10}{'日期':<12}{'股价':<8}{'MA5':<8}{'MA10':<8}{'MA30':<8}"
                f"{'MA5%':<8}{'间距%':<8}{'涨幅%':<8}{'量比':<8}{'量级':<12}{'评分':<8}"
            )
            rows.append("-" * 150)

            for idx, s in enumerate(stocks, 1):
                d = s.extra_fields
                line = (
                    f"{idx:<6}{s.stock_name[:14]:<16}{s.stock_code:<10}{d.get('latest_date', 'N/A'):<12}"
                    f"{s.screen_price:>6.2f}  {d.get('ma5', 0):>6.2f}  {d.get('ma10', 0):>6.2f}  {d.get('ma30', 0):>6.2f}  "
                    f"{d.get('ma5_gap', 0):>6.2f}%  {d.get('ma_spread', 0):>6.2f}%  {d.get('recent_return', 0):>6.2f}%  "
                    f"{d.get('vol_ratio', 0):>5.2f}  {d.get('volume_level', 'N/A'):<12}{s.score:>6.2f}"
                )
                rows.append(line)
        else:
            rows.append("=== 当前无符合条件的趋势股 ===")
        return rows

    # 同时输出所有格式
    try:
        repo = get_repository()
        results = output_mgr.output_all(repo=repo, table_formatter=format_trend_table)
        print(f"\n✓ TXT: {results['txt']}")
        print(f"✓ CSV: {results['csv']}")
        print(f"✓ 数据库记录ID: {results['screening_id']}")
    except Exception as e:
        # 如果数据库操作失败，至少输出文件
        print(f"注意: 数据库写入失败 ({e})，仅输出文件")
        results = output_mgr.output_all(table_formatter=format_trend_table)
        print(f"\n✓ TXT: {results['txt']}")
        print(f"✓ CSV: {results['csv']}")

    # 输出到控制台（原有格式）
    print('\n')
    print('\n'.join(output_mgr._generate_txt_content(format_trend_table)))
    print("")
    print("=" * 130)
    print("筛选条件说明:")
    print("  1. 多头排列   - MA5 > MA10 > MA30")
    print("  2. 均线上升   - 三条均线均向上")
    print("  3. 市场过滤   - 剔除创业板(300xxx)、科创板(688xxx)、ST股票")
    print("")
    print("评分说明 (总分115分):")
    print("  - MA间距得分 (35分): MA5与MA30的间距越大，多头排列越强")
    print("  - 股价位置得分 (25分): 股价在MA5上方越远，趋势越强")
    print("  - 近期涨幅得分 (25分): 近期涨幅越大，趋势越明显")
    print("  - 成交量得分 (15分): 量比越大，资金关注度越高")
    print("      · 巨量(≥2.0): 15分  · 明显放量(≥1.5): 12分")
    print("      · 轻度放量(≥1.2): 8分   · 正常(≥1.0): 5分  · 缩量: 2分")
    print("")
    print("量比说明: 当日成交量 / 5日均量")
    print("=" * 130)


if __name__ == "__main__":
    main()
