# -*- coding: utf-8 -*-
"""
读取交易记录
"""
import pandas as pd
import sys

try:
    # 读取Excel文件
    file_path = r"D:\Documents\trading\Table.xls"
    print(f"正在读取: {file_path}\n")

    # 尝试不同的读取方式
    try:
        df = pd.read_excel(file_path)
    except:
        # 如果失败，尝试用其他引擎
        df = pd.read_excel(file_path, engine='xlrd')

    print("="*80)
    print("交易记录")
    print("="*80)
    print(f"\n总记录数: {len(df)}")
    print(f"列名: {list(df.columns)}\n")

    print("-"*80)
    print(df.to_string())
    print("-"*80)

    # 基本统计
    print("\n" + "="*80)
    print("统计摘要")
    print("="*80)

    # 尝试找数值列
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if numeric_cols:
        print(f"\n数值列: {numeric_cols}")
        print("\n数值统计:")
        print(df[numeric_cols].describe())

    # 显示前几条和后几条
    print("\n" + "="*80)
    print("前5条记录:")
    print("="*80)
    print(df.head())

    print("\n" + "="*80)
    print("后5条记录:")
    print("="*80)
    print(df.tail())

except Exception as e:
    print(f"读取失败: {e}")
    import traceback
    traceback.print_exc()

    # 尝试作为文本文件读取
    print("\n" + "="*80)
    print("尝试作为文本文件读取...")
    print("="*80)
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            print(content[:5000])  # 只显示前5000字符
    except:
        with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
            content = f.read()
            print(content[:5000])
