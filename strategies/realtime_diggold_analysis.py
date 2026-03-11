#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用掘金SDK获取真实股票数据进行实时强弱分析
"""

import sys
import os
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入掘金SDK
try:
    from gm.api import set_token, history_n
    GM_SDK_AVAILABLE = True
except ImportError:
    GM_SDK_AVAILABLE = False
    print("警告: 掘金SDK未安装")

# 导入配置
from data.config_data_source import DATA_SOURCE_CONFIG
import config.realtime_strength_config as cfg

# 测试股票列表
TEST_STOCKS = {
    'SHSE.600644': '乐山电力',
    'SZSE.000818': '航锦科技',
    'SZSE.002202': '金风科技',
    'SZSE.000988': '华工科技',
}


class RealtimeStrengthAnalyzer:
    """实时股票强弱分析器（使用掘金SDK真实数据）"""

    def __init__(self):
        self.MA_SHORT = cfg.MA_SHORT
        self.MA_LONG = cfg.MA_LONG
        self.MACD_FAST = cfg.MACD_FAST
        self.MACD_SLOW = cfg.MACD_SLOW
        self.MACD_SIGNAL = cfg.MACD_SIGNAL
        self.RSI_PERIOD = cfg.RSI_PERIOD
        self.BOLL_PERIOD = cfg.BOLL_PERIOD
        self.BOLL_STD = cfg.BOLL_STD
        self.ADX_PERIOD = cfg.ADX_PERIOD
        self.ATR_PERIOD = cfg.ATR_PERIOD

        # 初始化掘金SDK
        if GM_SDK_AVAILABLE:
            token = DATA_SOURCE_CONFIG['sources']['diggold']['token']
            if token:
                set_token(token)
                print("掘金SDK初始化成功")
            else:
                print("警告: DIGGOLD_TOKEN未配置")

    def fetch_real_data(self, symbol, count=100):
        """从掘金SDK获取真实历史数据"""
        if not GM_SDK_AVAILABLE:
            return None

        try:
            end_date = datetime.now().strftime('%Y-%m-%d')
            data = history_n(
                symbol=symbol,
                frequency='60s',  # 1分钟K线
                count=count,
                end_time=end_date,
                df=True
            )

            if data is not None and not data.empty:
                # 处理数据格式
                if 'eob' in data.columns:
                    data['datetime'] = pd.to_datetime(data['eob'])
                elif 'bob' in data.columns:
                    data['datetime'] = pd.to_datetime(data['bob'])

                # 确保所有必要列都存在
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                for col in required_cols:
                    if col not in data.columns:
                        data[col] = 0

                return data
            else:
                print(f"  警告: 未获取到 {symbol} 的数据")
                return None

        except Exception as e:
            print(f"  获取数据失败: {e}")
            return None

    def analyze(self, df):
        """分析股票强弱"""
        if df is None or len(df) < 30:
            return None

        # 提取价格序列
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        volume = df['volume'].values.astype(float)

        try:
            # 计算技术指标
            ma_short = ta.sma(pd.Series(close), length=self.MA_SHORT).values
            ma_long = ta.sma(pd.Series(close), length=self.MA_LONG).values

            # MACD
            macd_result = ta.macd(pd.Series(close), fast=self.MACD_FAST, slow=self.MACD_SLOW, signal=self.MACD_SIGNAL)
            macd = macd_result.iloc[:, 0].values if not macd_result.empty else np.zeros(len(close))
            macd_signal = macd_result.iloc[:, 1].values if len(macd_result.columns) > 1 else np.zeros(len(close))
            macd_hist = macd_result.iloc[:, 2].values if len(macd_result.columns) > 2 else np.zeros(len(close))

            # RSI
            rsi = ta.rsi(pd.Series(close), length=self.RSI_PERIOD).values

            # 布林带
            boll = ta.bbands(pd.Series(close), length=self.BOLL_PERIOD, std=self.BOLL_STD)
            if boll is not None and not boll.empty:
                upper = boll.iloc[:, 0].values
                lower = boll.iloc[:, 2].values if len(boll.columns) > 2 else boll.iloc[:, 0].values
            else:
                upper = np.full(len(close), np.nan)
                lower = np.full(len(close), np.nan)

            # ADX
            adx_result = ta.adx(pd.Series(high), pd.Series(low), pd.Series(close), length=self.ADX_PERIOD)
            adx = adx_result.iloc[:, 0].values if not adx_result.empty else np.full(len(close), 20)

            # ATR
            atr_result = ta.atr(pd.Series(high), pd.Series(low), pd.Series(close), length=self.ATR_PERIOD)
            atr = atr_result.values if not atr_result.empty else np.zeros(len(close))

            # 获取最新值
            current_price = close[-1]
            current_ma_short = ma_short[-1] if not pd.isna(ma_short[-1]) else close[-1]
            current_ma_long = ma_long[-1] if not pd.isna(ma_long[-1]) else close[-1]
            current_macd = macd[-1] if not pd.isna(macd[-1]) else 0
            current_macd_signal = macd_signal[-1] if not pd.isna(macd_signal[-1]) else 0
            current_macd_hist = macd_hist[-1] if not pd.isna(macd_hist[-1]) else 0
            current_rsi = rsi[-1] if not pd.isna(rsi[-1]) else 50
            current_upper = upper[-1]
            current_lower = lower[-1]
            current_adx = adx[-1] if not pd.isna(adx[-1]) else 20
            current_atr = atr[-1] if not pd.isna(atr[-1]) else 0

            # 计算涨跌幅
            if len(close) >= 2:
                change_pct = ((close[-1] - close[-2]) / close[-2]) * 100
            else:
                change_pct = 0

            # 计算强弱评分
            trend_score = self._calculate_trend_score(current_ma_short, current_ma_long,
                                                      current_macd, current_macd_signal,
                                                      current_macd_hist, current_adx)

            momentum_score = self._calculate_momentum_score(current_rsi, current_price,
                                                            current_upper, current_lower)

            volume_score = self._calculate_volume_score(volume)

            volatility_score = self._calculate_volatility_score(current_atr, current_price)

            # 综合强弱评分
            overall_strength = (
                trend_score * 0.35 +
                momentum_score * 0.30 +
                volume_score * 0.20 +
                volatility_score * 0.15
            )

            return {
                'price': current_price,
                'change_pct': change_pct,
                'trend_score': trend_score,
                'momentum_score': momentum_score,
                'volume_score': volume_score,
                'volatility_score': volatility_score,
                'overall_strength': overall_strength,
                'rsi': current_rsi,
                'adx': current_adx,
                'macd_hist': current_macd_hist,
                'ma_diff_pct': ((current_ma_short / current_ma_long) - 1) * 100 if current_ma_long > 0 else 0
            }

        except Exception as e:
            print(f"  计算技术指标失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_trend_score(self, ma_short, ma_long, macd, macd_signal, macd_hist, adx):
        """计算趋势强度评分"""
        score = 50
        if ma_short > ma_long:
            score += 15
        else:
            score -= 15
        if macd > macd_signal:
            score += 15
            if macd_hist > 0:
                score += 5
        else:
            score -= 15
        if adx > 25:
            score += min(15, (adx - 25) / 2)
        return max(0, min(100, score))

    def _calculate_momentum_score(self, rsi, price, upper, lower):
        """计算动量强度评分"""
        score = 50
        if rsi > 50:
            score += (rsi - 50) * 0.5
        else:
            score -= (50 - rsi) * 0.5
        if pd.notna(upper) and pd.notna(lower):
            boll_width = upper - lower
            if boll_width > 0:
                if price > upper:
                    score += 10
                elif price < lower:
                    score -= 10
                else:
                    position = (price - lower) / boll_width
                    score += (position - 0.5) * 20
        return max(0, min(100, score))

    def _calculate_volume_score(self, volume):
        """计算成交量强度评分"""
        if len(volume) < 5:
            return 50
        recent_vol = volume[-1]
        avg_vol = np.mean(volume[-5:])
        if avg_vol > 0:
            if recent_vol > avg_vol * 1.2:
                return 75 + min(25, (recent_vol / avg_vol - 1.2) * 50)
            elif recent_vol < avg_vol * 0.8:
                return 25 - min(25, (1 - recent_vol / avg_vol) * 50)
            else:
                return 50
        return 50

    def _calculate_volatility_score(self, atr, price):
        """计算波动率强度评分"""
        if pd.isna(atr) or price == 0:
            return 50
        atr_pct = (atr / price) * 100
        if 1 < atr_pct < 3:
            return 60 + min(40, (atr_pct - 1) * 20)
        elif atr_pct >= 3:
            return 50
        else:
            return max(0, atr_pct * 30)

    def print_analysis(self, symbol, name, analysis):
        """打印分析结果"""
        strength = analysis['overall_strength']
        change_pct = analysis.get('change_pct', 0)

        # 强弱评级
        if strength >= 75:
            rating = "[超强]"
        elif strength >= 60:
            rating = "[强势]"
        elif strength >= 45:
            rating = "[中性]"
        elif strength >= 30:
            rating = "[弱势]"
        else:
            rating = "[超弱]"

        # 涨跌幅显示
        change_str = f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%"

        print(f"\n{'='*70}")
        print(f"  {rating} {name} ({symbol})")
        print(f"{'='*70}")
        print(f"  当前价格: {analysis['price']:.2f} 元  ({change_str})")
        print(f"  综合评分: {strength:.1f}/100")
        print(f"\n  [分项评分]")
        print(f"    趋势强度: {analysis['trend_score']:.1f}/100  |  动量强度: {analysis['momentum_score']:.1f}/100")
        print(f"    成交量:   {analysis['volume_score']:.1f}/100  |  波动率:   {analysis['volatility_score']:.1f}/100")
        print(f"\n  [关键指标]")
        print(f"    RSI: {analysis['rsi']:.1f}  |  ADX: {analysis['adx']:.1f}  |  MACD柱: {analysis['macd_hist']:.4f}")
        print(f"    MA偏离: {analysis['ma_diff_pct']:.2f}%")

        # 交易建议
        print(f"\n  [交易建议]")
        if strength >= 70:
            print(f"    [!] 强势股，注意追高风险")
        elif strength >= 55:
            print(f"    [OK] 趋势向上，可逢低关注")
        elif strength >= 45:
            print(f"    [--] 震荡整理，观望为主")
        elif strength >= 30:
            print(f"    [X] 趋势转弱，注意风险")
        else:
            print(f"    [XX] 走势疲软，不建议介入")

        print(f"{'='*70}")


def main():
    """主函数"""
    print("\n" + "="*70)
    print("  股票实时强弱分析系统 - 掘金SDK真实数据")
    print("  分析股票: 乐山电力、航锦科技、金风科技、华工科技")
    print("  数据时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("="*70)

    if not GM_SDK_AVAILABLE:
        print("\n错误: 掘金SDK不可用，请先安装 gm 包")
        return

    analyzer = RealtimeStrengthAnalyzer()
    results = []

    for symbol, name in TEST_STOCKS.items():
        print(f"\n正在分析 {name} ({symbol})...")

        # 获取真实数据
        df = analyzer.fetch_real_data(symbol, count=100)

        if df is not None and not df.empty:
            print(f"  获取数据: {len(df)} 条K线")

            # 执行分析
            analysis = analyzer.analyze(df)

            if analysis:
                analyzer.print_analysis(symbol, name, analysis)
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'strength': analysis['overall_strength'],
                    'price': analysis['price'],
                    'change_pct': analysis.get('change_pct', 0)
                })
        else:
            print(f"  跳过: 未获取到数据")

    # 汇总排名
    if results:
        print(f"\n\n{'='*70}")
        print("  [强弱排名汇总]")
        print(f"{'='*70}")
        results.sort(key=lambda x: x['strength'], reverse=True)
        for i, r in enumerate(results, 1):
            rank = ['No.1', 'No.2', 'No.3'][i-1] if i <= 3 else f'No.{i}'
            change_str = f"+{r['change_pct']:.2f}%" if r['change_pct'] >= 0 else f"{r['change_pct']:.2f}%"
            print(f"  {rank} {r['name']:8s} - 评分: {r['strength']:.1f}/100  |  价格: {r['price']:.2f}  ({change_str})")

    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
