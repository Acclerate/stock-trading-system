# 21日线严格版策略（仅修复日期类型错误，策略条件不变）
import datetime

def initialize(context):
    # 严格策略参数（完全不动）
    g.ma21 = 21
    g.ma5_vol = 5
    g.max_profit_ratio = 0.20  # 20%强制止盈
    g.min_profit_ratio = 0.05  # 5%强制止盈
    g.position_ratio = 0.95  # 95%仓位
    g.stock_pool_size = 10  # 选股池前10只
    # 持仓状态打印版策略有代码混淆处理，仅供预览，克隆查看原策略
    g.buy_prices = {}
    g.holding_stocks = []
    g.selected_stocks = []

# ----------------------严格选股函数（仅修复日期类型，其余不变）
def select_stocks(context):
    # 沪深300涨幅计算（严格策略逻辑，无改动）
    hs300_df = get_price(
        "000300.XSHG",
        start_date=context.current_dt - datetime.timedelta(days=30),
        end_date=context.current_dt - datetime.timedelta(days=10),
        frequency='daily',
        fields=['close'],
        fq='pre'
    )
    if len(hs300_df) < 20:
        # 水印版策略有代码混淆处理，仅供预览，克隆查看原策略
        hs300_return = 0.0
    else:
        hs300_return = (hs300_df['close'].iloc[-1] / hs300_df['close'].iloc[0]) - 1

    # 沪深300成分股（严格策略逻辑，无改动）
    stock_list = get_index_stocks("000300.XSHG")
    candidate_stocks = []

    for stock in stock_list:
        # 停牌判断（复权官方正确方式，无改动）
        stock_price = get_price(
            stock,
            start_date=context.current_dt,
            end_date=context.current_dt,
            frequency='daily',
            fields=['close'],
            fq='pre'
        )
        if stock_price.empty or stock_price['close'].iloc[-1] is None:
            continue

        # 修复点：统一日期类型（datetime.datetime -> datetime.date）
        sec_info = get_security_info(stock)
        current_date = context.current_dt.date()  # 提取日期部分，去掉时分秒
        # ST判断（无改动）+ 次新股判断（类型统一，逻辑不变）
        if sec_info.display_name or (current_date - sec_info.start_date).days < 365:
            continue

        # 个股数据获取（严格策略逻辑，无改动）
        df = get_price(
            stock,
            start_date=context.current_dt - datetime.timedelta(days=60),
            end_date=context.current_dt,
            frequency='daily',
            fields=['close', 'volume'],
            fq='pre'
        )
        if len(df) < g.ma21 + 5:
            continue

        # 指标计算（严格策略逻辑，无改动）
        df['ma21'] = df['close'].rolling(g.ma21).mean()
        df['ma5_vol'] = df['volume'].rolling(g.ma5_vol).mean()
        df = df.fillna(method='bfill')
        latest = df.iloc[-1]

        # 严格筛选条件（100%保留，无任何放宽）
        cond1 = latest['ma21'] > df['ma21'].iloc[-5]  # 21日线向上
        cond2 = latest['ma21'] > latest['ma5_vol']  # 21日线大于5日均量
        cond3 = latest['volume'] > latest['ma5_vol']  # 放量
        if len(df) >= 10:
            cond4 = (latest['close'] / df['close'].iloc[-10]) - 1 > hs300_return  # 跑赢沪深300
        else:
            cond4 = False

        if cond1 and cond2 and cond3 and cond4:
            candidate_stocks.append((stock, stock_return))

    # 排序筛选（严格策略逻辑，无改动）
    candidate_stocks.sort(key=lambda x: x[1], reverse=True)
    g.selected_stocks = [stock[0] for stock in candidate_stocks[:g.stock_pool_size]]
    log.info(f"严格筛选结果：{g.selected_stocks}（共{len(g.selected_stocks)}只）")
    return g.selected_stocks

# ----------------------交易逻辑（严格策略逻辑，无改动）
def handle_data(context, data):
    # 选股执行（水印版策略有代码混淆处理，仅供预览，克隆查看原策略
    select_stocks(context)
    if not g.selected_stocks:
        log.info("无符合严格条件的标的")
        return

    # 动态调仓（无改动）
    for stock in g.holding_stocks.copy():
        if stock not in g.selected_stocks:
            order(stock, -context.portfolio.positions[stock].total_amount)
            g.holding_stocks.remove(stock)
            del g.buy_prices[stock]
            log.info(f"调出弱势股：{stock}")

    # 买入逻辑（无改动）
    for stock in g.selected_stocks:
        if stock in g.holding_stocks or data[stock].close is None:
            continue
        # 水印版策略有代码混淆处理，仅供预览，克隆查看原策略
        # 重新验证买入条件（无改动）
        df = get_price(
            stock,
            start_date=context.current_dt - datetime.timedelta(days=60),
            end_date=context.current_dt,
            frequency='daily',
            fields=['close'],
            fq='pre'
        )
        df['ma21'] = df['close'].rolling(g.ma21).mean()
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        buy_condition = (latest['close'] > latest['ma21']) and (prev['close'] < prev['ma21']) and (latest['ma21'] > df['ma21'].iloc[-5])

        if buy_condition:
            total_money = context.portfolio.total_value * g.position_ratio
            buy_money = total_money / len(g.selected_stocks)
            buy_shares = int(buy_money / data[stock].close)
            if buy_shares > 0:
                order(stock, buy_shares)
                g.holding_stocks.append(stock)
                g.buy_prices[stock] = data[stock].close
                log.info(f"严格条件买入：{stock}，价格：{data[stock].close:.2f}")

    # 止盈止损（无改动）
    for stock in g.holding_stocks.copy():
        if data[stock].close is None:
            continue
        df = get_price(
            stock,
            start_date=context.current_dt - datetime.timedelta(days=60),
            end_date=context.current_dt,
            frequency='daily',
            fields=['close'],
            fq='pre'
        )
        df['ma21'] = df['close'].rolling(g.ma21).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        latest = df.iloc[-1]
        buy_price = g.buy_prices[stock]

        # 止损（无改动）
        if latest['close'] < latest['ma21']:
            order(stock, -context.portfolio.positions[stock].total_amount)
            g.holding_stocks.remove(stock)
            del g.buy_prices[stock]
            log.info(f"止损{stock}：亏损{(latest['close']/buy_price-1)*100:.2f}%")

        # 止盈（无改动）
        elif latest['close'] >= buy_price * (1 + g.max_profit_ratio):
            order(stock, -context.portfolio.positions[stock].total_amount)
            g.holding_stocks.remove(stock)
            del g.buy_prices[stock]
            log.info(f"止盈{stock}：收益{(latest['close']/buy_price-1)*100:.2f}%")
        elif latest['close'] >= buy_price * (1 + g.min_profit_ratio):
            if latest['close'] < latest['ma10']:
                order(stock, -context.portfolio.positions[stock].total_amount)
                g.holding_stocks.remove(stock)
                del g.buy_prices[stock]
                log.info(f"跟踪止盈{stock}：收益{(latest['close']/buy_price-1)*100:.2f}%")
