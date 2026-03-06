#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
每日策略自动执行脚本
在每个交易日晚上9点开始依次执行六个策略：
1. 21:00 - 沪深300筛选（生成缓存）
2. 21:10 - 中证500筛选（生成缓存）
3. 21:20 - 趋势股筛选（扫描全A股）
4. 21:30 - 低位放量突破（机构策略）
5. 21:45 - 快速选股（基于缓存）
6. 22:00 - 多维评分分析（深度分析）
"""
import sys
import os
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# 设置项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 配置日志
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"daily_screen_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ========== 策略配置 ==========
STRATEGIES = [
    {
        'name': '沪深300筛选',
        'type': 'hs300_screen',
        'script': 'strategies/stockPre.py',
        'args': ['--pool', 'hs300', '--days', '365'],
        'description': '沪深300成分股筛选（生成缓存）',
        'schedule_time': '21:00'
    },
    {
        'name': '中证500筛选',
        'type': 'zz500_screen',
        'script': 'strategies/stockPre.py',
        'args': ['--pool', 'zz500', '--days', '365'],
        'description': '中证500成分股筛选（生成缓存）',
        'schedule_time': '21:10'
    },
    {
        'name': '趋势股筛选',
        'type': 'trend_stocks',
        'script': 'strategies/trend_stocks.py',
        'args': ['--days', '60', '--min-strength', '0.6'],
        'description': '趋势股筛选（扫描全A股）',
        'schedule_time': '21:20'
    },
    {
        'name': '低位放量突破',
        'type': 'low_volume_breakout',
        'script': 'strategies/low_volume_breakout/main.py',
        'args': [
            '--mode', 'institutional',
            '--min-cap', '20.0',
            '--max-cap', '500.0',
            '--low-threshold', '0.6',
            '--volume-ratio', '1.5',
            '--data-period', '1000',
            '--no-trend-filter',
            '--min-turnover', '0.5',
            '--max-volatility', '50.0',
            '--no-volume-progressive',
            '--include-chinext'
        ],
        'description': '机构级低位放量突破策略',
        'schedule_time': '21:30'
    },
    {
        'name': '快速选股',
        'type': 'quick_select',
        'script': 'strategies/quick_select.py',
        'args': ['--use-cache'],
        'description': '快速选股（基于缓存）',
        'schedule_time': '21:45'
    },
    {
        'name': '多维评分分析',
        'type': 'stock_ranking',
        'script': 'strategies/stockRanking.py',
        'args': [],
        'description': '多维评分深度分析',
        'schedule_time': '22:00'
    }
]


def run_strategy(strategy_config: dict) -> bool:
    """
    执行单个策略

    Args:
        strategy_config: 策略配置字典

    Returns:
        执行是否成功
    """
    name = strategy_config['name']
    script = strategy_config['script']
    args = strategy_config['args']

    logger.info("=" * 60)
    logger.info(f"开始执行: {name}")
    logger.info(f"脚本: {script}")
    logger.info(f"参数: {' '.join(args)}")
    logger.info("=" * 60)

    script_path = PROJECT_ROOT / script

    if not script_path.exists():
        logger.error(f"脚本不存在: {script_path}")
        return False

    try:
        # 构建命令
        cmd = [sys.executable, str(script_path)] + args

        # 执行命令
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=1800  # 30分钟超时
        )

        # 记录输出
        if result.stdout:
            logger.info(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"STDERR:\n{result.stderr}")

        if result.returncode == 0:
            logger.info(f"✅ {name} 执行成功")
            return True
        else:
            logger.error(f"❌ {name} 执行失败 (返回码: {result.returncode})")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"❌ {name} 执行超时 (30分钟)")
        return False
    except Exception as e:
        logger.error(f"❌ {name} 执行异常: {e}")
        return False


def main():
    """主函数"""
    start_time = datetime.now()
    logger.info("")
    logger.info("=" * 60)
    logger.info("每日策略自动执行开始")
    logger.info(f"执行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"待执行策略数量: {len(STRATEGIES)}")
    logger.info("=" * 60)
    logger.info("")

    # 执行结果统计
    results = {
        'success': [],
        'failed': []
    }

    # 依次执行每个策略
    for idx, strategy in enumerate(STRATEGIES, 1):
        logger.info(f"\n[{idx}/{len(STRATEGIES)}] 执行策略: {strategy['name']}")

        success = run_strategy(strategy)

        if success:
            results['success'].append(strategy['type'])
        else:
            results['failed'].append(strategy['type'])

        logger.info("")

    # 输出汇总
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info("=" * 60)
    logger.info("执行完成汇总")
    logger.info("=" * 60)
    logger.info(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"总耗时: {duration/60:.1f} 分钟")
    logger.info(f"成功: {len(results['success'])} 个")
    logger.info(f"失败: {len(results['failed'])} 个")

    if results['success']:
        logger.info(f"成功策略: {', '.join(results['success'])}")

    if results['failed']:
        logger.error(f"失败策略: {', '.join(results['failed'])}")

    logger.info("=" * 60)

    # 返回退出码（有失败时返回非0）
    return 0 if not results['failed'] else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\n执行被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n未捕获的异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
