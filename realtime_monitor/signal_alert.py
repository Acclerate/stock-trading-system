"""
信号提醒模块

支持多种提醒方式：控制台输出、日志文件记录。

当交易信号发生变化时，自动发送提醒。
"""

import os
from datetime import datetime
from typing import Dict, Optional
from .indicator_engine import IndicatorEngine


class SignalAlert:
    """信号提醒类"""

    def __init__(self, enable_console: bool = True, enable_log: bool = True, log_dir: str = None):
        """
        初始化信号提醒

        参数:
            enable_console: 是否启用控制台输出
            enable_log: 是否启用日志记录
            log_dir: 日志目录路径
        """
        self.enable_console = enable_console
        self.enable_log = enable_log
        self.log_dir = log_dir or 'logs/signals'

        # 确保日志目录存在
        if self.enable_log:
            os.makedirs(self.log_dir, exist_ok=True)

    def send_alert(self, symbol: str, name: str, current_signal: Dict,
                   prev_signal: Optional[Dict] = None, price: float = None,
                   timestamp: datetime = None):
        """
        发送信号提醒

        参数:
            symbol: 股票代码
            name: 股票名称
            current_signal: 当前信号 {'signal': 'buy/sell/hold', 'score': 0-6, 'reason': '...'}
            prev_signal: 前一个信号
            price: 当前价格
            timestamp: 时间戳
        """
        # 判断是否为有效信号变化
        if prev_signal and self._get_signal_value(current_signal) == self._get_signal_value(prev_signal):
            return  # 信号未变化，不提醒

        # 使用当前时间
        if timestamp is None:
            timestamp = datetime.now()

        # 构造提醒消息
        message = self._format_alert_message(
            symbol, name, current_signal, prev_signal, price, timestamp
        )

        # 控制台输出
        if self.enable_console:
            print(message)

        # 日志记录
        if self.enable_log:
            self._log_alert(symbol, name, current_signal, price, timestamp)

    def _get_signal_value(self, signal: Dict) -> str:
        """获取信号值（用于比较信号是否变化）"""
        if signal is None:
            return None
        return signal.get('signal', 'hold')

    def _format_alert_message(self, symbol: str, name: str, current_signal: Dict,
                              prev_signal: Optional[Dict], price: Optional[float],
                              timestamp: datetime) -> str:
        """格式化提醒消息"""
        signal_type = current_signal.get('signal', 'hold')
        emoji = IndicatorEngine.get_signal_emoji(signal_type)
        description = IndicatorEngine.get_signal_description(
            signal_type,
            current_signal.get('score', 0)
        )

        lines = [
            "=" * 60,
            f"{emoji} 信号提醒 - {timestamp.strftime('%H:%M:%S')}",
            "=" * 60,
            f"股票: {name} ({symbol})",
        ]

        if price is not None:
            lines.append(f"价格: {price:.2f} 元")

        lines.extend([
            f"信号: {signal_type.upper()}",
            f"评分: {current_signal.get('score', 0)}/6",
            f"原因: {current_signal.get('reason', '无')}",
        ])

        if prev_signal:
            lines.append(
                f"变化: {prev_signal.get('signal', 'hold').upper()} -> {signal_type.upper()}"
            )

        lines.append("=" * 60)

        return '\n'.join(lines)

    def _log_alert(self, symbol: str, name: str, signal: Dict, price: Optional[float], timestamp: datetime):
        """记录信号到日志文件"""
        log_file = os.path.join(self.log_dir, f"{timestamp.strftime('%Y%m%d')}_signals.log")

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                price_str = f"{price:.2f}" if price is not None else "N/A"
                f.write(
                    f"{timestamp.isoformat()} | {symbol} | {name} | "
                    f"{signal['signal']} | {signal['score']} | {signal['reason']} | "
                    f"price:{price_str}\n"
                )
        except Exception as e:
            print(f"⚠️ 写入日志失败: {e}")

    def send_batch_alerts(self, signals: list, timestamp: datetime = None):
        """
        批量发送信号提醒

        参数:
            signals: 信号列表 [{'symbol': '', 'name': '', 'signal': {...}, 'price': 0, 'prev_signal': {...}}]
            timestamp: 时间戳
        """
        if timestamp is None:
            timestamp = datetime.now()

        if not signals:
            return

        # 批量模式：只输出有变化的信号
        changed_signals = [s for s in signals if self._should_alert(s)]

        if not changed_signals:
            return

        # 批量输出标题
        print(f"\n{'=' * 60}")
        print(f"📊 批量信号更新 - {timestamp.strftime('%H:%M:%S')}")
        print(f"{'=' * 60}")

        for item in changed_signals:
            self.send_alert(
                symbol=item['symbol'],
                name=item['name'],
                current_signal=item['signal'],
                prev_signal=item.get('prev_signal'),
                price=item.get('price'),
                timestamp=timestamp
            )

    def _should_alert(self, signal_item: dict) -> bool:
        """判断是否应该发送提醒"""
        current = signal_item['signal']
        prev = signal_item.get('prev_signal')

        return self._get_signal_value(current) != self._get_signal_value(prev)


def format_change_bar(change: float) -> str:
    """
    生成涨跌图形

    参数:
        change: 涨跌幅百分比

    返回:
        图形字符串
    """
    if change > 0:
        bars = int(change / 2)
        return "📈" + "█" * min(bars, 10)
    elif change < 0:
        bars = int(abs(change) / 2)
        return "📉" + "▓" * min(bars, 10)
    else:
        return "➡️"
