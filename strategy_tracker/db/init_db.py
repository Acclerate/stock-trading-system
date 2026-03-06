"""
数据库初始化脚本
创建数据库表结构
支持 SQLite 和 MySQL
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from strategy_tracker.config import DB_CONFIG, get_database_url
from strategy_tracker.db.repository import DatabaseRepository


def init_database():
    """初始化数据库表"""
    print("=" * 60)
    print("策略跟踪系统 - 数据库初始化")
    print("=" * 60)
    print()
    print(f"数据库类型: {DB_CONFIG['type'].upper()}")

    if DB_CONFIG['type'] == 'sqlite':
        db_path = Path(DB_CONFIG['sqlite_path'])
        print(f"数据库文件: {db_path}")
        print(f"文件大小: {db_path.stat().st_size if db_path.exists() else 0} 字节")
    else:
        print(f"数据库地址: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"数据库名称: {DB_CONFIG['database']}")

    print()

    try:
        repo = DatabaseRepository()

        # 检查连接
        print("正在连接数据库...")
        from sqlalchemy import text
        with repo.get_session() as session:
            session.execute(text("SELECT 1"))
        print("[OK] 数据库连接成功")
        print()

        # 创建表
        print("正在创建数据表...")
        repo.create_tables()
        print("[OK] 数据表创建成功")
        print()

        print("创建的表:")
        print("  - screening_records  (筛选记录表)")
        print("  - stock_positions    (股票持仓表)")
        print("  - return_records     (收益记录表)")
        print("  - benchmark_data     (基准数据表)")
        print("  - strategy_stats     (策略统计表)")
        print()

        if DB_CONFIG['type'] == 'sqlite':
            print("提示: SQLite 数据文件已创建")
            print(f"      备份时只需复制该文件即可")

        print("=" * 60)
        print("数据库初始化完成!")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def drop_database():
    """删除数据库表（谨慎使用）"""
    print("=" * 60)
    print("警告: 即将删除所有数据表!")
    print("=" * 60)
    print()

    if DB_CONFIG['type'] == 'sqlite':
        print("SQLite: 将删除所有表，但数据库文件会保留")
    else:
        print("MySQL/PostgreSQL: 将删除所有表，数据库保留")

    print()

    confirm = input("确认删除? (输入 'yes' 确认): ")
    if confirm.lower() != 'yes':
        print("已取消")
        return

    try:
        repo = DatabaseRepository()
        print("正在删除数据表...")
        repo.drop_tables()
        print("[OK] 数据表删除成功")

    except Exception as e:
        print(f"[ERROR] 删除失败: {e}")


def check_database():
    """检查数据库状态"""
    print("=" * 60)
    print("数据库状态检查")
    print("=" * 60)
    print()

    try:
        repo = DatabaseRepository()

        from sqlalchemy import inspect
        inspector = inspect(repo.engine)

        tables = inspector.get_table_names()

        if not tables:
            print("数据库中暂无表，请先运行初始化")
            print("  运行命令: python -m strategy_tracker.db.init_db init")
            return

        print(f"已创建的表 ({len(tables)} 个):")
        for table in tables:
            print(f"  - {table}")

        print()

        # 统计记录数
        with repo.get_session() as session:
            for table in tables:
                from sqlalchemy import text
                result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"  {table}: {count} 条记录")

        print()

        if DB_CONFIG['type'] == 'sqlite':
            db_path = Path(DB_CONFIG['sqlite_path'])
            if db_path.exists():
                size_mb = db_path.stat().st_size / (1024 * 1024)
                print(f"数据库文件大小: {size_mb:.2f} MB")

    except Exception as e:
        print(f"[ERROR] 检查失败: {e}")
        import traceback
        traceback.print_exc()


def backup_database():
    """备份数据库（仅SQLite）"""
    if DB_CONFIG['type'] != 'sqlite':
        print("备份功能仅支持 SQLite")
        return

    print("=" * 60)
    print("备份数据库")
    print("=" * 60)
    print()

    import shutil
    from datetime import datetime

    db_path = Path(DB_CONFIG['sqlite_path'])
    if not db_path.exists():
        print("数据库文件不存在")
        return

    # 创建备份目录
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"stock_tracker_backup_{timestamp}.db"

    try:
        shutil.copy2(db_path, backup_path)
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f"[OK] 备份成功")
        print(f"  备份文件: {backup_path}")
        print(f"  文件大小: {size_mb:.2f} MB")
    except Exception as e:
        print(f"[ERROR] 备份失败: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='策略跟踪系统数据库管理')
    parser.add_argument('action', nargs='?', default='init',
                        choices=['init', 'drop', 'check', 'backup'],
                        help='操作: init=初始化, drop=删除表, check=检查状态, backup=备份(SQLite)')

    args = parser.parse_args()

    if args.action == 'init':
        init_database()
    elif args.action == 'drop':
        drop_database()
    elif args.action == 'check':
        check_database()
    elif args.action == 'backup':
        backup_database()
