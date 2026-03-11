#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时股票强弱分析系统
使用掘金SDK事件驱动模式获取实时行情并进行强弱分析

功能：
- 实时订阅股票行情
- 多维度技术分析（趋势、动量、成交量、波动率）
- 智能告警系统
- 数据持久化存储
"""

import sys
import os
import pandas as pd
import numpy as np
import pandas_ta as ta
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path

# Windows声音告警模块
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 掘金SDK导入
try:
    from gm.api import init, subscribe
    GM_AVAILABLE = True
except ImportError:
    GM_AVAILABLE = False
    # 模拟模式的mock函数
    def subscribe(*args, **kwargs):
        """模拟模式的subscribe函数"""
        pass
    def init(*args, **kwargs):
        """模拟模式的init函数"""
        pass

# 导入配置
import config.realtime_strength_config as cfg

# ========== 设置日志 ==========
# 确保日志目录存在
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / cfg.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 导入数据源（用于获取历史数据初始化）
# 注意：如果掘金SDK未安装，会跳过历史数据预加载
DiggoldDataSource = None
try:
    from data.diggold_data import DiggoldDataSource
except ImportError:
    logger.warning("掘金SDK未安装，历史数据预加载功能不可用")

# ========== 确保输出目录存在 ==========
OUTPUT_DIR = PROJECT_ROOT / cfg.OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ========== 全局状态 ==========
# 存储每只股票的历史数据
price_data = {}

# 存储分析历史
analysis_history = []

# 告警冷却记录
alert_history = {}

# 数据保存计数器
save_counter = 0

# 上一价格记录（用于计算涨跌幅）
prev_prices = {}

# ========== 状态管理类 ==========

class GlobalState:
    """全局状态管理类，用于在掘金SDK回调和主程序间共享状态"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.price_data = {}
            cls._instance.analysis_history = []
            cls._instance.alert_history = {}
            cls._instance.save_counter = 0
            cls._instance.prev_prices = {}
        return cls._instance

    @classmethod
    def reset(cls):
        """重置状态"""
        cls._instance = None


# ========== 掘金SDK策略类 ==========

class RealtimeStrengthStrategy:
    """实时强弱分析策略类（掘金SDK事件驱动模式）"""

    def __init__(self, symbols, frequency='60s'):
        """
        初始化策略

        参数:
            symbols: 订阅的股票列表
            frequency: K线频率
        """
        self.symbols = symbols
        self.frequency = frequency
        self.state = GlobalState()

        # 从配置读取技术指标参数
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

    def init(self, context):
        """
        策略初始化回调（掘金SDK调用）

        参数:
            context: 策略上下文对象
        """
        logger.info("=" * 70)
        logger.info("实时股票强弱分析系统启动")
        logger.info("=" * 70)
        logger.info(f"订阅股票数量: {len(self.symbols)}")
        logger.info(f"K线频率: {self.frequency}")
        logger.info(f"技术指标参数: MA({self.MA_SHORT},{self.MA_LONG}), MACD({self.MACD_FAST},{self.MACD_SLOW},{self.MACD_SIGNAL}), RSI({self.RSI_PERIOD})")
        logger.info("=" * 70)

        # 预加载历史数据（可选，加快首次分析速度）
        self._preload_historical_data()

        # 订阅股票行情
        subscribe(self.symbols, frequency=self.frequency)
        logger.info(f"已订阅 {len(self.symbols)} 只股票的实时行情")

    def _preload_historical_data(self):
        """预加载历史数据"""
        if DiggoldDataSource is None:
            logger.info("掘金SDK未安装，跳过历史数据预加载")
            return

        logger.info("正在预加载历史数据...")
        try:
            # 获取最近的100条1小时K线数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')

            for symbol in self.symbols:
                try:
                    df = DiggoldDataSource.get_stock_history(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        frequency='1800s',  # 30分钟K线
                        adjust=DiggoldDataSource.ADJUST_PREV
                    )

                    if not df.empty:
                        # 确保数据格式正确
                        df = self._prepare_dataframe(df)
                        self.state.price_data[symbol] = df
                        logger.info(f"  {symbol}: 预加载 {len(df)} 条历史数据")
                except Exception as e:
                    logger.warning(f"  {symbol}: 预加载失败 ({e})")

            logger.info("历史数据预加载完成")
        except Exception as e:
            logger.warning(f"预加载历史数据失败: {e}")

    def _prepare_dataframe(self, df):
        """准备DataFrame格式"""
        # 确保必要的列存在
        required_cols = ['open', 'high', 'low', 'close', 'volume']

        # 如果有date索引，重置为列
        if df.index.name == 'date':
            df = df.reset_index()

        # 确保有datetime列
        if 'datetime' not in df.columns:
            if 'date' in df.columns:
                df['datetime'] = pd.to_datetime(df['date'])
            else:
                df['datetime'] = pd.date_range(start=datetime.now(), periods=len(df), freq='1min')

        # 确保所有必要列都存在
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0

        return df

    def on_bar(self, bar):
        """
        K线数据推送回调（掘金SDK调用）

        参数:
            bar: K线数据对象
        """
        try:
            symbol = bar.symbol

            # 更新该股票的价格数据
            if symbol not in self.state.price_data:
                self.state.price_data[symbol] = pd.DataFrame()

            # 获取前一个价格（用于涨跌幅计算）
            prev_price = None
            if len(self.state.price_data[symbol]) > 0:
                prev_price = self.state.price_data[symbol].iloc[-1]['close']
                self.state.prev_prices[symbol] = prev_price
            elif symbol in self.state.prev_prices:
                prev_price = self.state.prev_prices[symbol]

            # 添加新的K线数据
            new_row = {
                'datetime': pd.to_datetime(bar.eob) if hasattr(bar, 'eob') else datetime.now(),
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': float(bar.volume)
            }

            self.state.price_data[symbol] = pd.concat([
                self.state.price_data[symbol],
                pd.DataFrame([new_row])
            ], ignore_index=True)

            # 限制数据窗口大小
            if len(self.state.price_data[symbol]) > cfg.DATA_WINDOW_SIZE:
                self.state.price_data[symbol] = self.state.price_data[symbol].tail(cfg.DATA_WINDOW_SIZE).reset_index(drop=True)

            # 确保有足够的数据进行技术分析
            if len(self.state.price_data[symbol]) >= cfg.MIN_BARS_FOR_ANALYSIS:
                # 执行强弱分析
                analysis = self.analyze_strength(symbol, self.state.price_data[symbol])

                # 检查告警
                alerts = self.check_alert(symbol, analysis, prev_price)

                # 输出分析结果
                self.print_analysis(symbol, analysis, alerts)

                # 记录到历史
                if cfg.ENABLE_DATA_PERSISTENCE:
                    record = {
                        'symbol': symbol,
                        'timestamp': datetime.now().isoformat(),
                        'price': analysis['price'],
                        'overall_strength': analysis['overall_strength'],
                        'trend_score': analysis['trend_score'],
                        'momentum_score': analysis['momentum_score'],
                        'volume_score': analysis['volume_score'],
                        'volatility_score': analysis['volatility_score'],
                        'rsi': analysis['rsi'],
                        'adx': analysis['adx'],
                        'macd_hist': analysis['macd_hist'],
                        'ma_diff_pct': analysis['ma_diff_pct'],
                        'alerts': alerts
                    }
                    self.state.analysis_history.append(record)

            # 定期保存数据
            self.state.save_counter += 1
            if self.state.save_counter >= cfg.SAVE_INTERVAL:
                self.save_analysis_data()
                self.state.save_counter = 0

        except Exception as e:
            logger.error(f"处理K线数据时出错: {e}")
            import traceback
            traceback.print_exc()

    def on_tick(self, tick):
        """
        分笔数据推送回调（掘金SDK调用）

        参数:
            tick: 分笔数据对象
        """
        # 暂不处理分笔数据，如需实现可在此添加
        pass

    def on_order(self, order):
        """委托回调"""
        pass

    def on_trade(self, trade):
        """成交回调"""
        pass

    def on_stop(self, context):
        """策略停止回调"""
        logger.info("策略停止，保存剩余数据...")
        self.save_analysis_data()

    # ========== 分析方法 ==========

    def analyze_strength(self, symbol, df):
        """
        分析股票强弱

        参数:
            symbol: 股票代码
            df: 历史K线数据

        返回:
            分析结果字典
        """
        # 提取价格序列
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        volume = df['volume'].values.astype(float)

        # 计算技术指标
        try:
            # 使用pandas_ta计算技术指标
            # 移动平均线
            ma_short = ta.sma(pd.Series(close), length=self.MA_SHORT).values
            ma_long = ta.sma(pd.Series(close), length=self.MA_LONG).values

            # MACD
            macd_result = ta.macd(pd.Series(close), fast=self.MACD_FAST, slow=self.MACD_SLOW, signal=self.MACD_SIGNAL)
            macd = macd_result[f'MACD_{self.MACD_FAST}_{self.MACD_SLOW}_{self.MACD_SIGNAL}'].values if f'MACD_{self.MACD_FAST}_{self.MACD_SLOW}_{self.MACD_SIGNAL}' in macd_result.columns else np.zeros(len(close))
            macd_signal = macd_result[f'MACDs_{self.MACD_FAST}_{self.MACD_SLOW}_{self.MACD_SIGNAL}'].values if f'MACDs_{self.MACD_FAST}_{self.MACD_SLOW}_{self.MACD_SIGNAL}' in macd_result.columns else np.zeros(len(close))
            macd_hist = macd_result[f'MACDh_{self.MACD_FAST}_{self.MACD_SLOW}_{self.MACD_SIGNAL}'].values if f'MACDh_{self.MACD_FAST}_{self.MACD_SLOW}_{self.MACD_SIGNAL}' in macd_result.columns else np.zeros(len(close))

            # RSI
            rsi = ta.rsi(pd.Series(close), length=self.RSI_PERIOD).values

            # 布林带
            boll = ta.bbands(pd.Series(close), length=self.BOLL_PERIOD, std=self.BOLL_STD)
            if boll is not None and not boll.empty:
                upper = boll[f'BBU_{self.BOLL_PERIOD}_{self.BOLL_STD}'].values if f'BBU_{self.BOLL_PERIOD}_{self.BOLL_STD}' in boll.columns else np.full(len(close), np.nan)
                lower = boll[f'BBL_{self.BOLL_PERIOD}_{self.BOLL_STD}'].values if f'BBL_{self.BOLL_PERIOD}_{self.BOLL_STD}' in boll.columns else np.full(len(close), np.nan)
            else:
                upper = np.full(len(close), np.nan)
                lower = np.full(len(close), np.nan)

            # ADX
            adx_result = ta.adx(pd.Series(high), pd.Series(low), pd.Series(close), length=self.ADX_PERIOD)
            adx = adx_result[f'ADX_{self.ADX_PERIOD}'].values if f'ADX_{self.ADX_PERIOD}' in adx_result.columns else np.full(len(close), 20)

            # ATR
            atr_result = ta.atr(pd.Series(high), pd.Series(low), pd.Series(close), length=self.ATR_PERIOD)
            atr = atr_result[f'ATRr_{self.ATR_PERIOD}'].values if f'ATRr_{self.ATR_PERIOD}' in atr_result.columns else atr_result.iloc[:, 0].values if not atr_result.empty else np.zeros(len(close))

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

            # 计算强弱评分（0-100）
            trend_score = self.calculate_trend_score(current_ma_short, current_ma_long,
                                                     current_macd, current_macd_signal,
                                                     current_macd_hist, current_adx)

            momentum_score = self.calculate_momentum_score(current_rsi, current_price,
                                                           current_upper, current_lower)

            volume_score = self.calculate_volume_score(volume)

            volatility_score = self.calculate_volatility_score(current_atr, current_price)

            # 综合强弱评分
            overall_strength = (
                trend_score * 0.35 +
                momentum_score * 0.30 +
                volume_score * 0.20 +
                volatility_score * 0.15
            )

            return {
                'price': current_price,
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
            logger.error(f"计算技术指标失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'price': df['close'].iloc[-1],
                'trend_score': 50,
                'momentum_score': 50,
                'volume_score': 50,
                'volatility_score': 50,
                'overall_strength': 50,
                'rsi': 50,
                'adx': 20,
                'macd_hist': 0,
                'ma_diff_pct': 0
            }

    def calculate_trend_score(self, ma_short, ma_long, macd, macd_signal, macd_hist, adx):
        """计算趋势强度评分"""
        score = 50  # 基准分

        # 均线多头排列
        if ma_short > ma_long:
            score += 15
        else:
            score -= 15

        # MACD金叉
        if macd > macd_signal:
            score += 15
            if macd_hist > 0:  # 柱状图为正
                score += 5
        else:
            score -= 15

        # ADX趋势强度
        if adx > 25:
            score += min(15, (adx - 25) / 2)  # 趋势明显加分

        return max(0, min(100, score))

    def calculate_momentum_score(self, rsi, price, upper, lower):
        """计算动量强度评分"""
        score = 50

        # RSI强弱
        if rsi > 50:
            score += (rsi - 50) * 0.5  # 50-70加分
        else:
            score -= (50 - rsi) * 0.5  # 30-50减分

        # BOLL位置
        if pd.notna(upper) and pd.notna(lower):
            boll_width = upper - lower
            if boll_width > 0:
                if price > upper:
                    score += 10  # 突破上轨强势
                elif price < lower:
                    score -= 10  # 跌破下轨弱势
                else:
                    # 在通道内按比例评分
                    position = (price - lower) / boll_width
                    score += (position - 0.5) * 20

        return max(0, min(100, score))

    def calculate_volume_score(self, volume):
        """计算成交量强度评分"""
        if len(volume) < 5:
            return 50

        # 与5日平均成交量比较
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

    def calculate_volatility_score(self, atr, price):
        """计算波动率强度评分"""
        if pd.isna(atr) or price == 0:
            return 50

        # ATR占价格的百分比
        atr_pct = (atr / price) * 100

        # 适度波动加分（有波动才有机会）
        if 1 < atr_pct < 3:
            return 60 + min(40, (atr_pct - 1) * 20)
        elif atr_pct >= 3:
            return 50  # 过高波动中性
        else:
            return max(0, atr_pct * 30)

    # ========== 告警方法 ==========

    def check_alert(self, symbol, analysis, prev_price=None):
        """检查并触发告警"""
        alerts = []
        now = datetime.now()

        # 初始化该股票的告警历史
        if symbol not in self.state.alert_history:
            self.state.alert_history[symbol] = {}

        # 1. 强弱告警
        if analysis['overall_strength'] >= cfg.ALERT_THRESHOLDS['strong']:
            if self._should_alert(symbol, 'strong', now):
                alerts.append(f"强势告警: 综合评分 {analysis['overall_strength']:.1f}")
                self._play_alert_sound('strong')

        elif analysis['overall_strength'] <= cfg.ALERT_THRESHOLDS['weak']:
            if self._should_alert(symbol, 'weak', now):
                alerts.append(f"弱势告警: 综合评分 {analysis['overall_strength']:.1f}")
                self._play_alert_sound('weak')

        # 2. RSI告警
        if analysis['rsi'] >= cfg.ALERT_THRESHOLDS['rsi_overbought']:
            if self._should_alert(symbol, 'rsi_overbought', now):
                alerts.append(f"RSI超买: {analysis['rsi']:.1f}")
                self._play_alert_sound('warning')

        elif analysis['rsi'] <= cfg.ALERT_THRESHOLDS['rsi_oversold']:
            if self._should_alert(symbol, 'rsi_oversold', now):
                alerts.append(f"RSI超卖: {analysis['rsi']:.1f}")
                self._play_alert_sound('warning')

        # 3. 涨跌幅告警（需要前一个价格）
        if prev_price and prev_price > 0:
            change_pct = ((analysis['price'] - prev_price) / prev_price) * 100
            if change_pct >= cfg.ALERT_THRESHOLDS['surge']:
                if self._should_alert(symbol, 'surge', now):
                    alerts.append(f"短期暴涨: +{change_pct:.2f}%")
                    self._play_alert_sound('surge')

            elif change_pct <= cfg.ALERT_THRESHOLDS['plunge']:
                if self._should_alert(symbol, 'plunge', now):
                    alerts.append(f"短期暴跌: {change_pct:.2f}%")
                    self._play_alert_sound('plunge')

        # 打印告警
        for alert in alerts:
            logger.warning(f" [{symbol}] {alert}")

        return alerts

    def _should_alert(self, symbol, alert_type, now):
        """检查是否应该触发告警（考虑冷却时间）"""
        if symbol not in self.state.alert_history:
            self.state.alert_history[symbol] = {}

        if alert_type not in self.state.alert_history[symbol]:
            self.state.alert_history[symbol][alert_type] = now
            return True

        last_alert = self.state.alert_history[symbol][alert_type]
        if (now - last_alert).total_seconds() >= cfg.ALERT_COOLDOWN:
            self.state.alert_history[symbol][alert_type] = now
            return True

        return False

    def _play_alert_sound(self, alert_type):
        """播放告警声音（Windows）"""
        if not cfg.ENABLE_SOUND_ALERT or not WINSOUND_AVAILABLE:
            return

        try:
            if alert_type in ['strong', 'surge']:
                winsound.Beep(1000, 200)  # 高音
            elif alert_type in ['weak', 'plunge']:
                winsound.Beep(300, 300)   # 低音
            else:
                winsound.Beep(600, 150)   # 中音
        except:
            pass  # 如果无法播放声音，静默失败

    # ========== 输出方法 ==========

    def print_analysis(self, symbol, analysis, alerts=None):
        """输出分析结果"""
        strength = analysis['overall_strength']

        # 强弱评级
        if strength >= 75:
            rating = "超强"
        elif strength >= 60:
            rating = "强势"
        elif strength >= 45:
            rating = "中性"
        elif strength >= 30:
            rating = "弱势"
        else:
            rating = "超弱"

        print(f"\n{'='*60}")
        print(f" {symbol} @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        print(f"  当前价格: {analysis['price']:.2f}")
        print(f"  强弱评级: {rating} ({strength:.1f}/100)")
        print(f"\n  【分项评分】")
        print(f"    趋势强度: {analysis['trend_score']:.1f} (MA/MACD/ADX)")
        print(f"    动量强度: {analysis['momentum_score']:.1f} (RSI/BOLL)")
        print(f"    成交量:   {analysis['volume_score']:.1f}")
        print(f"    波动率:   {analysis['volatility_score']:.1f}")
        print(f"\n  【关键指标】")
        print(f"    RSI: {analysis['rsi']:.1f} | ADX: {analysis['adx']:.1f}")
        print(f"    MACD柱: {analysis['macd_hist']:.4f}")
        print(f"    MA偏离: {analysis['ma_diff_pct']:.2f}%")

        if alerts:
            print(f"\n  【告警】")
            for alert in alerts:
                print(f"    ! {alert}")

        print(f"{'='*60}")

    # ========== 数据持久化方法 ==========

    def save_analysis_data(self):
        """保存分析数据到文件"""
        if not self.state.analysis_history:
            return

        # 生成文件名（按日期）
        date_str = datetime.now().strftime('%Y%m%d')
        output_file = OUTPUT_DIR / f"analysis_{date_str}.jsonl"

        try:
            # 追加写入（JSON Lines格式）
            with open(output_file, 'a', encoding='utf-8') as f:
                for record in self.state.analysis_history:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')

            logger.info(f"已保存 {len(self.state.analysis_history)} 条分析记录到 {output_file}")
        except Exception as e:
            logger.error(f"保存数据失败: {e}")

        # 清空已保存的历史
        self.state.analysis_history.clear()


# ========== 模拟运行模式（用于测试） ==========

class SimulatorMode:
    """模拟运行模式（不依赖掘金SDK）"""

    def __init__(self, symbols, frequency='60s'):
        self.symbols = symbols
        self.frequency = frequency
        self.strategy = RealtimeStrengthStrategy(symbols, frequency)
        self.running = False
        self.state = GlobalState()

    def run(self):
        """模拟运行"""
        logger.info("=" * 70)
        logger.info("实时股票强弱分析系统 - 模拟模式")
        logger.info("=" * 70)
        logger.info(f"订阅股票: {', '.join(self.symbols)}")
        logger.info("按 Ctrl+C 停止\n")

        # 模拟初始化
        self.strategy.init(None)

        self.running = True
        try:
            import time
            while self.running:
                # 模拟生成K线数据
                for symbol in self.symbols:
                    if not self.running:
                        break

                    # 模拟Bar对象
                    class MockBar:
                        def __init__(self, symbol):
                            import random
                            self.symbol = symbol
                            base_price = 100 + random.random() * 900
                            self.open = base_price
                            self.high = base_price * (1 + random.random() * 0.02)
                            self.low = base_price * (1 - random.random() * 0.02)
                            self.close = base_price * (1 + (random.random() - 0.5) * 0.01)
                            self.volume = 1000000 + random.random() * 9000000
                            self.eob = datetime.now()

                    mock_bar = MockBar(symbol)
                    self.strategy.on_bar(mock_bar)

                # 等待下一个周期
                time.sleep(5)  # 5秒模拟一次

        except KeyboardInterrupt:
            logger.info("\n收到停止信号，正在保存数据...")
            self.strategy.on_stop(None)
            logger.info("程序已停止")


# ========== 主程序入口 ==========

def main():
    """主程序入口"""
    # 检查掘金SDK是否可用
    if not GM_AVAILABLE:
        logger.warning("掘金SDK未安装或不兼容，切换到模拟模式")
        simulator = SimulatorMode(cfg.STOCK_LIST, cfg.FREQUENCY)
        simulator.run()
        return

    # 检查Token
    from data.config_data_source import DATA_SOURCE_CONFIG
    token = DATA_SOURCE_CONFIG['sources']['diggold']['token']

    if not token:
        logger.error("DIGGOLD_TOKEN 未配置，请检查 .env 文件")
        logger.info("\n提示：")
        logger.info("1. 在项目根目录创建 .env 文件")
        logger.info("2. 添加内容: DIGGOLD_TOKEN=your_token_here")
        logger.info("3. 或切换到模拟模式进行测试")
        return

    # 创建策略实例
    strategy = RealtimeStrengthStrategy(cfg.STOCK_LIST, cfg.FREQUENCY)

    # 运行策略（通过掘金SDK）
    try:
        # 掘金SDK的run方法会调用init和on_bar等回调
        # 注意：这里需要根据掘金SDK的实际API调整
        logger.info("正在初始化掘金SDK...")

        # 设置Token
        from gm.api import set_token
        set_token(token)

        # 使用掘金SDK的策略运行模式
        # 注意：掘金SDK的策略运行方式可能需要调整
        from gm.api import run

        # 创建策略上下文并运行
        # 掘金SDK的策略类需要特定格式，这里使用回调方式
        def strategy_init(context):
            strategy.init(context)

        def strategy_on_bar(bar):
            strategy.on_bar(bar)

        def strategy_on_tick(tick):
            strategy.on_tick(tick)

        def strategy_on_stop(context):
            strategy.on_stop(context)

        # 注册策略回调
        # 注意：这里的API调用方式可能需要根据实际掘金SDK版本调整
        logger.info("启动实时监控...")
        logger.info("提示: 如果没有收到数据，请确保掘金终端已启动")

        # 尝试运行策略（如果掘金SDK版本支持）
        try:
            # 某些版本的掘金SDK可能需要不同的调用方式
            # 这里提供一种通用的调用方式
            import inspect

            # 检查run函数的签名
            run_sig = inspect.signature(run)
            if 'init' in run_sig.parameters:
                run(
                    init=strategy_init,
                    on_bar=strategy_on_bar,
                    on_tick=strategy_on_tick,
                    on_stop=strategy_on_stop
                )
            else:
                logger.info("掘金SDK版本不兼容，切换到模拟模式")
                simulator = SimulatorMode(cfg.STOCK_LIST, cfg.FREQUENCY)
                simulator.run()

        except Exception as e:
            logger.warning(f"掘金SDK运行失败: {e}")
            logger.info("切换到模拟模式进行测试...")
            simulator = SimulatorMode(cfg.STOCK_LIST, cfg.FREQUENCY)
            simulator.run()

    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 打印欢迎信息
    print("""
╔════════════════════════════════════════════════════════════╗
║         实时股票强弱分析系统 v1.0                          ║
║         Real-time Stock Strength Analysis System           ║
╠════════════════════════════════════════════════════════════╣
║  功能:                                                     ║
║    - 实时订阅股票行情                                      ║
║    - 多维度技术分析（趋势、动量、成交量、波动率）          ║
║    - 智能告警系统                                          ║
║    - 数据持久化存储                                        ║
╠════════════════════════════════════════════════════════════╣
║  使用:                                                     ║
║    1. 确保 .env 文件中配置了 DIGGOLD_TOKEN                ║
║    2. 启动掘金量化终端                                     ║
║    3. 在 config/realtime_strength_config.py 中配置股票列表 ║
║    4. 运行此脚本                                           ║
║    5. 按 Ctrl+C 停止                                       ║
╚════════════════════════════════════════════════════════════╝
""")

    main()
