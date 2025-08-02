class BacktestFramework:
    def __init__(self, commission=0.0001, slipper=1, hand_num=5, borrow_rate=0.0001):
        self.total_asset = None  # 初始资金
        self.available_asset = None  # 可用资金
        self.short_pos = 0  # 卖空仓位
        self.long_pos = 0  # 买多仓位
        self.commission = commission  # 手续费
        self.slipper = slipper  # 滑点
        self.hand_num = hand_num  # 每次操作手数
        self.back_data_set = None  # 回测数据集
        self.borrow_rate = borrow_rate  # 借入利率（每日）
        self.log = []  # 日志
        self.return_list = []  # 收益率结果
        self.tick_flow = None  # 时间流
        self.long_record=[]    #交易时间点记录
        self.short_record=[]
        self.close_record = []

    def set_back_data(self, data, asset_set):  # 设置回测数据集（必要！）
        self.back_data_set = data
        self.tick_flow = data.index
        self.total_asset = asset_set
        self.available_asset = asset_set  # 初始化可用资金

    def long_in(self, sign_index):
        if self.back_data_set is None:
            raise ValueError("Backtest data has not been set.")
        long_price = self.back_data_set.loc[sign_index + self.slipper, 'pa']  # pa 买入价格
        long_quant = 100 * self.hand_num * long_price  # 计算买入数量
        if self.available_asset * 0.95 < long_quant + long_quant * self.commission:
            return None  # 资金不足，无法买入
        else:
            self.long_pos += 100 * self.hand_num  # 更新买多仓位
            self.available_asset -= long_quant + long_quant * self.commission  # 扣除资金和手续费
            self.log.append(f'在{sign_index + self.slipper}时点买入 {long_quant}')
            return True  # 成功买入

    def short_in(self, sign_index):
        if self.back_data_set is None:
            raise ValueError("Backtest data has not been set.")
        short_price = self.back_data_set.loc[sign_index + self.slipper, 'pb']  # 卖空价格
        short_quant = 100 * self.hand_num * short_price  # 计算卖空数量
        self.short_pos += 100 * self.hand_num  # 更新卖空仓位
        self.available_asset += short_quant - short_quant * self.commission  # 增加资金并扣除手续费
        borrow_cost = self.short_pos * self.borrow_rate  # 借入利息
        self.available_asset -= borrow_cost
        self.log.append(f'在{sign_index + self.slipper}时点卖空 {short_quant}')
        return True  # 成功卖空

    def long_close(self, sign_index):  # 多头平仓
        if self.long_pos <= 0:
            return None  # 没有多头仓位，无法平仓
        long_close_price = self.back_data_set.loc[sign_index + self.slipper, 'pb']  # pb 卖出价格
        short_quant = long_close_price * 100 * self.hand_num
        self.long_pos -= 100 * self.hand_num  # 减去多头仓位
        self.available_asset += short_quant - short_quant * self.commission
        self.log.append(f'在{sign_index + self.slipper}时点卖出多头平仓 {short_quant}')
        return True

    def short_close(self, sign_index):  # 空头平仓
        if self.short_pos <= 0:
            return None  # 没有空头仓位，无法平仓
        short_close_price = self.back_data_set.loc[sign_index + self.slipper, 'pa']  # pa 买回价格
        short_quant = short_close_price * 100 * self.hand_num
        self.short_pos -= 100 * self.hand_num
        self.available_asset -= short_quant + short_quant * self.commission
        self.log.append(f'在{sign_index + self.slipper}时点买入空头平仓 {short_quant}')
        return True

    def calculate_total_asset(self, tick):  # 资产总值变化
        price_cal = self.back_data_set.loc[tick, 'pa']  # 使用当前价格计算资产总值
        self.total_asset = self.available_asset + self.long_pos * price_cal - self.short_pos * price_cal
        self.return_list.append(self.total_asset)  # 存储总资产值
        return self.total_asset

    def strategy(self, hand_num, reference, tick):
        self.hand_num = hand_num  # 自定义一次买卖手数   增加减少表示购买的激进程度
        signal_buy = 0.000301
        signal_sell = -0.000301
        fluent = 5
        column_name = f'return_{fluent}s'
        length_close = fluent * 2

        if tick - length_close in self.long_record:  # 如果前 5s 内有预测收益小于阈值，则卖出平仓
            self.long_close(tick)
            self.close_record.append(tick+self.slipper)
        if tick - length_close in self.short_record:  # 如果前 5s 内有预测收益大于阈值，则买入平仓
            self.short_close(tick)
            self.close_record.append(tick+self.slipper)
            

        # 检查 tick 是否在索引范围内
        if tick not in reference.index:
            return None
        else:
            if reference.loc[tick, column_name] >= signal_buy:  # 如果 5s 内预测收益大于阈值，买入
                self.long_in(tick)
                self.long_record.append(tick+self.slipper)
            if reference.loc[tick, column_name] <= signal_sell:  # 如果 5s 内预测收益小于阈值，卖出
                self.short_in(tick)
                self.short_record.append(tick+self.slipper)


    def run(self, hand_num, reference):
        if self.back_data_set is None or self.total_asset is None:
            raise Exception("back_data_set or total asset is None")
        for tick in self.tick_flow:
            self.strategy(hand_num, reference, tick)
            self.calculate_total_asset(tick)