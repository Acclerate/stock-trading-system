# 掘金量化技术指标参考文档

> 来源：https://bbs.myquant.cn/thread/2050
> 
> 目的：补充项目中未使用的选股/分析股技术指标

---

## 概述

掘金量化平台缺少一些常用的技术指标函数，本文档汇总了基于掘金框架编写的常用技术指标实现，可供项目中的策略开发参考使用。

**重要提示**：行情软件（如通达信）的一些指标是基于股票上市首日计算得到的，如果计算时只用小部分的时间序列，得到的结果和通达信软件是不一致的。为了保持一致，所有指标都应按照上市首日计算。

---

## 前期准备

```python
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *
import pandas as pd
import numpy as np

set_token('请输入你的token')
```

---

## 一、KDJ指标

### 原理
- 计算N日RSV = （今日收盘 - N日最低）/(N日最高-N日最低) * 100
- K = (1-(1/M1))*前一日K值 + 1/M1 * RSV
- D = (1-(1/M1))*前一日D值 + 1/M1 * K值
- J = 3 * K - 2 * D

### 实现代码

```python
def KDJ(symbol, N, M1, M2, end_time):
    '''
    计算KDJ指标公式
    输入： data <- dataframe，需包含开盘、收盘、最高、最低价
          N、M1、M2 <- int
          end_time <- str   结束时间
    输出： 将K、D、J合并到data后的dataframe
    '''
    # 取历史数据，取到上市首日
    data = history(symbol=symbol, frequency='1d', start_time='2005-01-01', 
                   end_time=end_time, fields='symbol,bob,close,low,high', df=True)

    # 计算前N日最低和最高，缺失值用前n日（n<N)最小值替代
    lowList = data['low'].rolling(N).min()
    lowList.fillna(value=data['low'].expanding().min(), inplace=True)
    highList = data['high'].rolling(N).max()
    highList.fillna(value=data['high'].expanding().max(), inplace=True)
    
    # 计算rsv
    rsv = (data['close'] - lowList) / (highList - lowList) * 100
    
    # 计算k,d,j
    data['kdj_k'] = rsv.ewm(alpha=1/M1, adjust=False).mean()  # ewm是指数加权函数
    data['kdj_d'] = data['kdj_k'].ewm(alpha=1/M2, adjust=False).mean()
    data['kdj_j'] = 3.0 * data['kdj_k'] - 2.0 * data['kdj_d']
    
    return data

# 测试
d = KDJ('DCE.y2101', 9, 3, 3, '2020-12-31')
```

### 应用场景
- **超买超卖判断**：K、D、J值大于80为超买，小于20为超卖
- **金叉死叉**：K线上穿D线为买入信号，下穿为卖出信号
- **J值极端**：J值大于100或小于0时，价格可能反转

---

## 二、MACD指标

### 原理
- 计算12日和26日的EMA数据
- EMA(12) = 2/(12+1) * 今日收盘价 + 11/(12+1) * 昨日EMA(12)
- EMA(26) = 2/(26+1) * 今日收盘价 + 25/(26+1) * 昨日EMA(26)
- DEA = 2/(9+1) * 今日DIFF + 8/(9+1) * 昨日DEA
- MACD = 2 * (DIFF-DEA)

**注意**：上市首日DIFF、DEA、MACD均为0，次日的EMA均按照上市首日的收盘价计算

### 实现代码

```python
def MACD(symbol, start_time, end_time):
    '''计算MACD指标
        输入参数：
            symbol <- str      标的代码（2005年以前上市的不可用）
            start_time <- str  起始时间
            end_time <- str    结束时间
        输出数据：
            macd <- dataframe  macd指标，包括DIFF、DEA、MACD
    '''
    # 取历史数据，取到上市首日
    data = history(symbol=symbol, frequency='1d', start_time='2005-01-01', 
                   end_time=end_time, fields='symbol,bob,close', df=True)
    
    # 将数据转化为dataframe格式
    data['bob'] = data['bob'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist()

    # 计算EMA(12)和EMA(26)
    data['EMA12'] = data['close'].ewm(alpha=2 / 13, adjust=False).mean()
    data['EMA26'] = data['close'].ewm(alpha=2 / 27, adjust=False).mean()

    # 计算DIFF、DEA、MACD
    data['DIFF'] = data['EMA12'] - data['EMA26']
    data['DEA'] = data['DIFF'].ewm(alpha=2 / 10, adjust=False).mean()
    data['MACD'] = 2 * (data['DIFF'] - data['DEA'])

    # 上市首日，DIFF、DEA、MACD均为0
    data['DIFF'].iloc[0] = 0
    data['DEA'].iloc[0] = 0
    data['MACD'].iloc[0] = 0

    # 按照起止时间筛选
    MACD = data[(data['bob'] >= start_time)]

    return MACD

# 测试
a = MACD(symbol='DCE.y2101', start_time='2020-01-01', end_time='2020-10-22')
```

### 应用场景
- **趋势判断**：DIFF上穿DEA（金叉）为买入信号，下穿（死叉）为卖出信号
- **背离信号**：价格创新高但MACD未创新高，可能见顶
- **零轴意义**：DIFF在零轴上方为多头市场，下方为空头市场

---

## 三、DMA指标

### 原理
- 计算DIF: close的N1日移动平均 - close的N2日移动平均
- 计算AMA: DIF的M日移动平均

### 实现代码

```python
def DMA(symbol, start_time, end_time, N1, N2, M):
    ''' 计算DMA
        输入参数：
            symbol <- str      标的代码
            start_time <- str  开始时间
            end_time <- str    结束时间
            N1 <- int          大周期均值
            N2 <- int          小周期均值
            M <- int           AMA周期
        输出参数：
            DMA <- dataframe
    '''
    # 取历史数据，取到上市首日
    data = history(symbol=symbol, frequency='1d', start_time='2005-01-01', 
                   end_time=end_time, fields='symbol,bob,close', df=True)
    
    data['MA1'] = data['close'].rolling(N1).mean()
    data['MA2'] = data['close'].rolling(N2).mean()
    data['DIF'] = data['MA1'] - data['MA2']
    data['AMA'] = data['DIF'].rolling(M).mean()

    # 将数据转化为dataframe格式
    data['bob'] = data['bob'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist()

    # 按起止时间筛选
    DMA = data[(data['bob'] >= start_time)]

    return DMA

# 测试
d1 = DMA(symbol='DCE.y2101', start_time='2020-01-01', end_time='2020-10-22', 
         N1=10, N2=50, M=6)
```

### 应用场景
- **趋势跟踪**：DMA向上交叉AMA为买入信号，向下交叉为卖出信号
- **参数设置**：常用参数为(10, 50, 6)，短周期跟踪短期趋势，长周期跟踪长期趋势

---

## 四、BIAS指标（乖离率）

### 原理
乖离率表示股价与移动平均线的偏离程度：
- BIAS = (收盘价 - N日移动平均) / N日移动平均 * 100

### 实现代码

```python
def BIAS(symbol, start_time, end_time, N1, N2, N3):
    '''计算BIAS指标
        输入参数：
            symbol <- str      标的代码
            start_time <- str  开始时间
            end_time <- str    结束时间
            N1, N2, N3 <- int  三条BIAS线的周期
        输出参数：
            BIAS <- dataframe
    '''
    # 取历史数据
    data = history(symbol=symbol, frequency='1d', start_time='2005-01-01', 
                   end_time=end_time, fields='symbol,bob,close', df=True)
    
    # 计算不同周期的移动平均线
    data['MA1'] = data['close'].rolling(N1).mean()
    data['MA2'] = data['close'].rolling(N2).mean()
    data['MA3'] = data['close'].rolling(N3).mean()
    
    # 计算BIAS
    data['BIAS1'] = (data['close'] - data['MA1']) / data['MA1'] * 100
    data['BIAS2'] = (data['close'] - data['MA2']) / data['MA2'] * 100
    data['BIAS3'] = (data['close'] - data['MA3']) / data['MA3'] * 100

    # 格式化日期
    data['bob'] = data['bob'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist()
    
    # 按起止时间筛选
    BIAS = data[(data['bob'] >= start_time)]
    
    return BIAS

# 常用参数：BIAS(6, 12, 24)
```

### 应用场景
- **超买超卖**：BIAS过大表示超买，过小表示超卖
- **参数选择**：短期BIAS(6日)反应灵敏，长期BIAS(24日)反应滞后但更稳定
- **结合使用**：多条BIAS线同时向上或向下交叉时信号更可靠

---

## 五、其他常用指标建议补充

### 1. RSI（相对强弱指标）
```python
def RSI(symbol, start_time, end_time, N=14):
    '''计算RSI指标
        RSI = 100 - 100/(1+RS)
        RS = N日内上涨幅度平均值 / N日内下跌幅度平均值
    '''
    data = history(symbol=symbol, frequency='1d', start_time='2005-01-01', 
                   end_time=end_time, fields='symbol,bob,close', df=True)
    
    # 计算涨跌幅
    data['change'] = data['close'].diff()
    
    # 分离上涨和下跌
    data['gain'] = data['change'].apply(lambda x: x if x > 0 else 0)
    data['loss'] = data['change'].apply(lambda x: -x if x < 0 else 0)
    
    # 计算平均涨跌
    avg_gain = data['gain'].rolling(N).mean()
    avg_loss = data['loss'].rolling(N).mean()
    
    # 计算RSI
    rs = avg_gain / avg_loss
    data['RSI'] = 100 - (100 / (1 + rs))
    
    return data
```

### 2. 布林带（BOLL）
```python
def BOLL(symbol, start_time, end_time, N=20, K=2):
    '''计算布林带指标
        中轨 = N日移动平均线
        上轨 = 中轨 + K * N日标准差
        下轨 = 中轨 - K * N日标准差
    '''
    data = history(symbol=symbol, frequency='1d', start_time='2005-01-01', 
                   end_time=end_time, fields='symbol,bob,close', df=True)
    
    data['MA'] = data['close'].rolling(N).mean()
    data['STD'] = data['close'].rolling(N).std()
    data['UPPER'] = data['MA'] + K * data['STD']
    data['LOWER'] = data['MA'] - K * data['STD']
    
    return data
```

### 3. 成交量指标（VOL）
```python
def VOL_MA(symbol, start_time, end_time, N1=5, N2=10):
    '''计算成交量移动平均线
        VOL_MA5 = 5日成交量平均
        VOL_MA10 = 10日成交量平均
    '''
    data = history(symbol=symbol, frequency='1d', start_time='2005-01-01', 
                   end_time=end_time, fields='symbol,bob,volume', df=True)
    
    data['VOL_MA5'] = data['volume'].rolling(N1).mean()
    data['VOL_MA10'] = data['volume'].rolling(N2).mean()
    
    return data
```

---

## 六、指标组合应用建议

### 多指标共振策略

| 指标组合 | 买入信号 | 卖出信号 |
|---------|---------|---------|
| KDJ + MACD | KDJ金叉且MACD金叉 | KDJ死叉且MACD死叉 |
| RSI + BOLL | RSI从超卖区回升且触及BOLL下轨 | RSI从超买区回落且触及BOLL上轨 |
| BIAS + DMA | BIAS负值过大且DMA金叉 | BIAS正值过大且DMA死叉 |
| MACD + VOL | MACD金叉且成交量放大 | MACD死叉且成交量萎缩 |

### 项目应用建议

1. **StockPre模块**：可加入KDJ超买超卖判断，增强买入信号过滤
2. **Stock Grain Ranking**：可引入BIAS和DMA进行趋势强度评分
3. **实时监控系统**：可结合RSI和BOLL进行实时预警
4. **回测系统**：可测试多指标共振策略的效果

---

## 七、注意事项

1. **数据长度**：计算指标时需要足够的历史数据，建议从2005年开始获取
2. **上市首日处理**：部分指标在上市首日需要特殊处理（如MACD设为0）
3. **复权处理**：计算指标前确保数据已进行前复权处理
4. **参数优化**：不同市场、不同品种可能需要调整参数
5. **信号过滤**：单一指标信号可能不准确，建议多指标共振确认

---

## 参考链接

- 掘金量化官方论坛：https://bbs.myquant.cn/thread/2050
- 掘金量化API文档：https://www.myquant.cn/docs/python/41
