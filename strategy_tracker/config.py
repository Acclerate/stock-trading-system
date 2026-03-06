"""
策略跟踪系统配置文件
读取环境变量配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录 (stockScience 目录)
# __file__ = strategy_tracker/config.py
# .parent = strategy_tracker/
# .parent.parent = stockScience/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# 数据库配置
DB_TYPE = os.getenv('DB_TYPE', 'sqlite')

DB_CONFIG = {
    'type': DB_TYPE,
    # SQLite 配置
    'sqlite_path': os.getenv('DB_PATH', str(DATA_DIR / 'stock_tracker.db')),
    # MySQL 配置（如果使用 MySQL）
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'stock_tracker'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'root'),
    'charset': 'utf8mb4',
}

# 数据库连接URL构建
def get_database_url():
    """获取SQLAlchemy数据库连接URL"""
    db_type = DB_CONFIG['type']

    if db_type == 'sqlite':
        # SQLite: 使用本地文件，无需安装服务
        sqlite_path = Path(DB_CONFIG['sqlite_path'])
        # 确保目录存在
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{sqlite_path}"

    elif db_type == 'mysql':
        # MySQL: 需要安装 MySQL 服务和 pymysql 驱动
        return (
            f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            f"?charset={DB_CONFIG['charset']}"
        )

    elif db_type == 'postgresql':
        # PostgreSQL: 需要安装 PostgreSQL 服务和 psycopg2 驱动
        return (
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        )

    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")

# 输出目录
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# 策略类型映射
STRATEGY_TYPES = {
    'hs300_screen': '沪深300筛选',
    'zz500_screen': '中证500筛选',
    'zz1000_screen': '中证1000筛选',
    'trend_stocks': '趋势股筛选',
    'low_volume_breakout': '低位放量突破',
    'stock_screen': '通用股票筛选',
}

# 持仓周期（天）
HOLDING_PERIODS = [5, 10, 20]

# 基准指数
BENCHMARK_INDEX = '000300'  # 沪深300

# 日期格式
DATE_FORMAT = '%Y-%m-%d'
DATE_FORMAT_COMPACT = '%Y%m%d'

# 数据文件模式（用于识别策略输出文件）
FILE_PATTERNS = {
    'hs300_screen': r'hs300_screen_\d{8}_\d{6}\.txt',
    'zz500_screen': r'zz500_screen_\d{8}_\d{6}\.txt',
    'zz1000_screen': r'zz1000_screen_\d{8}_\d{6}\.txt',
    'trend_stocks': r'trend_stocks_\d{8}_\d{6}\.txt',
    'low_volume_breakout': r'low_volume_breakout/stock_pool_\d{8}_\d{6}\.txt',
    'stock_screen': r'stock_screen_\d{8}_\d{6}\.txt',
}
