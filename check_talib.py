import talib

print("TA-Lib version:", talib.__version__)
print("\nAvailable technical indicators:")
functions = talib.get_functions()
print(f"Total functions: {len(functions)}")

# 相关指标
print("\nRelevant indicators:")
for func in ['MA', 'EMA', 'MACD', 'RSI', 'BBANDS', 'STDDEV']:
    if func in functions:
        print(f"  ✓ {func}")
