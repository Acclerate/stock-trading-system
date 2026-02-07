# -*- coding: utf-8 -*-
"""
分析交易记录
"""
import pandas as pd
from datetime import datetime
from collections import defaultdict

try:
    # 读取文件
    file_path = r"D:\Documents\trading\Table.xls"
    print("="*80)
    print("交易记录分析报告")
    print("="*80)

    # 尝试不同编码读取
    try:
        df = pd.read_csv(file_path, sep='\t', encoding='utf-8')
    except:
        try:
            df = pd.read_csv(file_path, sep='\t', encoding='gbk')
        except:
            df = pd.read_csv(file_path, sep='\t', encoding='utf-8', errors='ignore')

    print(f"\n总记录数: {len(df)} 条")

    # 重命名列
    columns_mapping = {
        '委托日期': 'date',
        '委托时间': 'time',
        '证券代码': 'code',
        '证券名称': 'name',
        '委托方向': 'direction',
        '委托数量': 'quantity',
        '委托状态': 'status',
        '委托价格': 'order_price',
        '成交数量': 'filled_quantity',
        '成交金额': 'filled_amount',
        '成交价格': 'filled_price'
    }

    # 找出实际存在的列并重命名
    actual_columns = {}
    for old_name in df.columns:
        if old_name in columns_mapping:
            actual_columns[old_name] = columns_mapping[old_name]
        else:
            actual_columns[old_name] = old_name

    df.rename(columns=actual_columns, inplace=True)

    print(f"列名: {list(df.columns)}\n")

    # 显示原始数据样本
    print("-"*80)
    print("原始数据前10条:")
    print("-"*80)
    print(df.head(10).to_string())
    print("-"*80)

    # 处理数据
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # 统计分析
    print("\n" + "="*80)
    print("交易统计")
    print("="*80)

    # 按股票统计
    if 'name' in df.columns:
        print("\n【按股票统计】")
        stock_stats = df.groupby('name').agg({
            'filled_quantity': 'sum' if 'filled_quantity' in df.columns else lambda x: 0,
            'filled_amount': 'sum' if 'filled_amount' in df.columns else lambda x: 0,
        }).round(2)
        print(stock_stats)

        # 交易最频繁的股票
        print("\n【交易最频繁的股票】")
        trade_count = df['name'].value_counts().head(10)
        print(trade_count)

    # 按方向统计
    if 'direction' in df.columns:
        print("\n【买卖方向统计】")
        direction_stats = df['direction'].value_counts()
        print(direction_stats)

    # 按日期统计
    if 'date' in df.columns:
        print("\n【交易日期分布】")
        date_stats = df.groupby(df['date'].dt.date).size()
        print(date_stats)

        print(f"\n交易时间范围: {df['date'].min()} 至 {df['date'].max()}")

    # 计算总交易金额
    if 'filled_amount' in df.columns:
        total_amount = df['filled_amount'].sum()
        print(f"\n总成交金额: {total_amount:,.2f} 元")

    # 成交统计
    if 'filled_quantity' in df.columns:
        df['filled'] = df['filled_quantity'] > 0
        filled_count = df['filled'].sum()
        fill_rate = (filled_count / len(df) * 100) if len(df) > 0 else 0
        print(f"成交率: {fill_rate:.2f}% ({filled_count}/{len(df)})")

    # 识别交易模式
    print("\n" + "="*80)
    print("交易模式分析")
    print("="*80)

    # 同一天多次交易同一只股票
    if 'date' in df.columns and 'name' in df.columns:
        df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
        same_day_trades = df.groupby(['date_str', 'name']).size().reset_index(name='count')
        same_day_frequent = same_day_trades[same_day_trades['count'] >= 3]

        if len(same_day_frequent) > 0:
            print("\n⚠️ 发现频繁交易（同一天同一股票交易3次以上）:")
            for _, row in same_day_frequent.iterrows():
                print(f"  {row['date_str']} - {row['name']}: {row['count']}次")

    # T+0回转交易检测
    print("\n【T+0回转交易检测】")
    if 'name' in df.columns and 'direction' in df.columns:
        # 按股票和日期排序
        df_sorted = df.sort_values(['name', 'date', 'time']) if 'time' in df.columns else df.sort_values(['name', 'date'])

        for stock in df_sorted['name'].unique():
            stock_data = df_sorted[df_sorted['name'] == stock]
            if len(stock_data) > 1:
                # 检查是否有买卖交替
                directions = stock_data['direction'].tolist()
                buy_sell_pattern = False
                for i in range(len(directions) - 1):
                    if '买' in str(directions[i]) and '卖' in str(directions[i+1]):
                        buy_sell_pattern = True
                        break
                    elif '卖' in str(directions[i]) and '买' in str(directions[i+1]):
                        buy_sell_pattern = True
                        break

                if buy_sell_pattern:
                    print(f"  {stock}: 存在买卖交替操作")

    # 分析建议
    print("\n" + "="*80)
    print("风险提示")
    print("="*80)

    risks = []

    # 检查交易频率
    if len(df) > 50:
        avg_trades_per_day = len(df) / 30  # 假设一个月
        if avg_trades_per_day > 5:
            risks.append(f"⚠️ 交易过于频繁：平均每天{avg_trades_per_day:.1f}笔交易")

    # 检查单一股票集中度
    if 'name' in df.columns:
        top_stock = df['name'].value_counts().iloc[0]
        total = len(df)
        if top_stock / total > 0.5:
            stock_name = df['name'].value_counts().index[0]
            risks.append(f"⚠️ 过度集中：{stock_name}占总交易{top_stock/total*100:.1f}%")

    # 检查是否有追涨杀跌
    if 'direction' in df.columns and 'name' in df.columns:
        for stock in df['name'].unique():
            stock_data = df[df['name'] == stock]
            if len(stock_data) >= 2:
                # 简单的价格变化检测
                if 'filled_price' in df.columns:
                    prices = stock_data['filled_price'].dropna()
                    if len(prices) >= 2:
                        price_change = (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0] * 100
                        if abs(price_change) > 20:
                            risks.append(f"⚠️ {stock}: 价格波动{price_change:+.1f}%，可能存在追涨杀跌")

    if risks:
        for risk in risks:
            print(risk)
    else:
        print("✓ 未发现明显风险")

    print("\n" + "="*80)
    print("分析完成")
    print("="*80)

except Exception as e:
    print(f"分析失败: {e}")
    import traceback
    traceback.print_exc()
