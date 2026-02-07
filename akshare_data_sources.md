# AkShare 数据源备选方案

## 当前使用的数据源

| 函数 | 数据源 | 域名 | 状态 |
|------|--------|------|------|
| `stock_zh_a_hist()` | 东方财富网 | push2his.eastmoney.com | ❌ 连接失败 |

## 可用的备选数据源

### 1. 东方财富网 - 备用接口

#### stock_zh_a_daily()
```python
df = ak.stock_zh_a_daily(symbol="sh600519", start_date="20240101", end_date="20241231", adjust="qfq")
```
- **数据源**: 东方财富网
- **域名**: quote.eastmoney.com
- **优点**: 与当前接口同一数据源，数据格式一致
- **缺点**: 可能受相同网络限制
- **参数**: 需要带市场前缀 (sh/sz)

### 2. 新浪财经

#### stock_zh_a_spot()
```python
df = ak.stock_zh_a_spot()
```
- **数据源**: 新浪财经
- **域名**: finance.sina.com.cn
- **优点**: 实时行情，数据更新快
- **缺点**: 仅提供实时数据，无历史K线

### 3. 网易财经

#### stock_zh_a_spot_fd()
```python
df = ak.stock_zh_a_spot_fd()
```
- **数据源**: 网易财经
- **域名**: money.163.com
- **优点**: 实时数据
- **缺点**: 历史数据接口不稳定

### 4. 腾讯财经

腾讯财经数据通常通过 `stock_zh_a_spot()` 聚合获取

### 5. 历史数据 - 其他接口

#### stock_zh_a_hist() 参数变体
```python
# 前复权
df = ak.stock_zh_a_hist(symbol="600519", period="daily", adjust="qfq")

# 后复权
df = ak.stock_zh_a_hist(symbol="600519", period="daily", adjust="hfq")

# 不复权
df = ak.stock_zh_a_hist(symbol="600519", period="daily", adjust="")
```

#### 不同周期
```python
# 周线
df = ak.stock_zh_a_hist(symbol="600519", period="weekly")

# 月线
df = ak.stock_zh_a_hist(symbol="600519", period="monthly")
```

### 6. 其他数据源库

#### Tushare（需要token）
```python
import tushare as ts
ts.set_token('your_token')
pro = ts.pro_api()
df = pro.daily(ts_code='600519.SH', start_date='20240101', end_date='20241231')
```
- **数据源**: Tushare官方
- **优点**: 数据质量高，接口稳定
- **缺点**: 需要注册获取token，免费版有限制

#### Efund（东方财富备用）
```python
import efinance as ef
df = ef.stock.get_quote_history('600519', beg='20240101', end='20241231')
```
- **数据源**: 东方财富
- **优点**: 轻量级，速度快
- **缺点**: 可能受相同网络限制

#### Baostock（证券宝）
```python
import baostock as bs
bs.login()
df = bs.query_history_k_data_plus('sh.600519',
    'date,open,high,low,close,volume',
    start_date='2024-01-01', end_date='2024-12-31')
bs.logout()
```
- **数据源**: Baostock官方
- **优点**: 免费，无需注册，接口稳定
- **缺点**: 数据更新有延迟

## 推荐方案

### 短期方案（当前网络问题）
1. **优先使用缓存数据**: `quick_select.py` 已验证可用
2. **尝试 Baostock**: 免费且稳定
3. **切换至 efinance**: 可能绕过当前网络限制

### 长期方案
1. **多数据源容错**: 实现自动切换机制
2. **本地数据库**: 存储历史数据，减少网络依赖
3. **Tushare Pro**: 如需高频/实时数据，考虑付费方案

## 修改 data_resilient.py 建议

```python
@staticmethod
def _fetch_with_retry(symbol: str, start_date: str, end_date: str, max_retries: int = 3):
    # 数据源优先级列表
    sources = [
        ('akshare_eastmoney', lambda: ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)),
        ('akshare_daily', lambda: ak.stock_zh_a_daily(symbol=f"sh{symbol}", start_date=start_date, end_date=end_date, adjust="qfq")),
        ('baostock', lambda: DataResilient._fetch_baostock(symbol, start_date, end_date)),
        ('efinance', lambda: DataResilient._fetch_efinance(symbol, start_date, end_date))
    ]

    for source_name, fetch_func in sources:
        for attempt in range(max_retries):
            try:
                df = fetch_func()
                if df is not None and not df.empty:
                    print(f"成功使用 {source_name} 获取数据")
                    return DataResilient._standardize_df(df)
            except Exception as e:
                print(f"{source_name} 失败: {str(e)[:50]}")
                time.sleep(random.uniform(1, 2))

    raise ValueError(f"所有数据源均失败: {symbol}")
```

## 测试建议

网络恢复后，按以下顺序测试：
1. `python test_akshare_sources.py` - 测试所有 akshare 接口
2. `python test_baostock.py` - 测试 baostock 接口
3. `python test_efinance.py` - 测试 efinance 接口
