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

前置条件：
1. 必须先打开东方财富终端
2. 点击"量化"进入掘金量化终端
3. 确保掘金终端正常运行
"""
import sys
import os
import subprocess
import logging
import time
from datetime import datetime
from pathlib import Path

# Windows控制台编码处理
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# 设置项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


# ========== 掘金终端连接检测 ==========
def check_diggold_terminal() -> bool:
    """
    检测掘金量化终端是否正常运行

    Returns:
        True: 终端可用
        False: 终端不可用或未启动
    """
    logger.info("=" * 60)
    logger.info("检测掘金量化终端连接状态...")
    logger.info("=" * 60)

    try:
        from gm.api import set_token, get_instruments

        # 设置Token
        token = os.getenv('DIGGOLD_TOKEN', '')
        if not token:
            logger.error("❌ DIGGOLD_TOKEN 环境变量未设置")
            logger.error("请在 .env 文件中配置 DIGGOLD_TOKEN")
            return False

        set_token(token)
        logger.info(f"Token已配置: {token[:16]}...")

        # 尝试获取股票列表来验证连接
        logger.info("正在连接掘金终端...")
        try:
            result = get_instruments(exchanges='SHSE', sec_types=1, df=True)
            if result is not None and len(result) > 0:
                logger.info(f"✅ 掘金终端连接成功! (获取到 {len(result)} 只股票)")
                return True
            else:
                logger.warning("⚠️ 掘金终端返回空数据")
                return False
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 掘金终端连接失败: {error_msg}")

            # 提供友好的错误提示
            if "连接" in error_msg or "网络" in error_msg or "timeout" in error_msg.lower():
                logger.error("")
                logger.error("【可能的解决方案】")
                logger.error("1. 请确保东方财富终端已打开")
                logger.error("2. 请点击终端内的'量化'按钮进入掘金量化终端")
                logger.error("3. 确认掘金量化终端处于正常运行状态")
                logger.error("")
                logger.error("或者运行: scripts\\start_with_terminal.bat")
                logger.error("该脚本会自动打开东方财富终端并等待就绪")
                logger.error("")

            return False

    except ImportError as e:
        logger.error(f"❌ 掘金SDK未安装: {e}")
        logger.error("请运行: pip install gm")
        return False
    except Exception as e:
        logger.error(f"❌ 检测过程发生异常: {e}")
        return False


def wait_for_terminal_ready(max_wait_seconds: int = 60) -> bool:
    """
    等待掘金终端就绪（用于启动终端后检测）

    Args:
        max_wait_seconds: 最大等待时间（秒）

    Returns:
        True: 终端就绪
        False: 超时未就绪
    """
    logger.info(f"等待掘金终端就绪 (最多等待 {max_wait_seconds} 秒)...")

    start_time = time.time()
    check_interval = 3  # 每3秒检测一次

    while time.time() - start_time < max_wait_seconds:
        if check_diggold_terminal():
            return True

        wait_time = int(time.time() - start_time)
        logger.info(f"等待中... ({wait_time}/{max_wait_seconds} 秒)")
        time.sleep(check_interval)

    logger.error(f"❌ 等待超时 ({max_wait_seconds} 秒)，掘金终端仍未就绪")
    return False

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
        'args': ['--days', '60'],
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

    # ========== 前置条件检查 ==========
    logger.info("【前置检查】")
    if not check_diggold_terminal():
        logger.error("")
        logger.error("=" * 60)
        logger.error("❌ 掘金终端连接检测失败!")
        logger.error("=" * 60)
        logger.error("")
        logger.error("请确保:")
        logger.error("  1. 东方财富终端已打开")
        logger.error("  2. 已点击'量化'进入掘金量化终端")
        logger.error("  3. DIGGOLD_TOKEN 已在 .env 文件中配置")
        logger.error("")
        logger.error("或使用启动脚本: scripts\\start_with_terminal.bat")
        logger.error("")
        return 1

    logger.info("")
    logger.info("✅ 前置检查通过，开始执行策略...")
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
