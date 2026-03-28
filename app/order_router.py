# 訂單路由模組（資金控管與訂單執行）
# 負責查詢帳戶資訊、計算目標股數、提交市價單

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from ib_insync import IB, MarketOrder, Stock

if TYPE_CHECKING:
    from app.config import Config
    from app.models import SignalPayload
    from app.notifier import Notifier

from app.models import OrderResult

logger = logging.getLogger(__name__)


class OrderRouter:
    """訂單路由器：根據帳戶資產與持倉狀態，計算並執行交易訂單。"""

    def __init__(self, ib: IB, config: Config, notifier: Notifier) -> None:
        """
        初始化 OrderRouter。

        Args:
            ib: ib_insync.IB 連線實例
            config: 應用程式設定（包含 use_equity_pct 等參數）
            notifier: 通知模組，用於發送交易與錯誤通知
        """
        self._ib = ib
        self._config = config
        self._notifier = notifier

    # ------------------------------------------------------------------
    # 公開方法
    # ------------------------------------------------------------------

    def calculate_target_shares(
        self, net_liquidation: float, market_price: float, use_equity_pct: float
    ) -> int:
        """
        計算目標持有股數。

        公式：floor(NetLiquidation × USE_EQUITY_PCT ÷ 市價)
        結果保證為非負整數。

        Args:
            net_liquidation: 帳戶淨資產值
            market_price: TQQQ 最新市價
            use_equity_pct: 使用資產比例（0~1）

        Returns:
            目標持有股數（非負整數）
        """
        if market_price <= 0:
            logger.warning("市價 <= 0 (%.4f)，目標股數設為 0", market_price)
            return 0

        target = math.floor(net_liquidation * use_equity_pct / market_price)
        # 確保非負
        return max(target, 0)

    def handle_entry(self, signal: SignalPayload) -> OrderResult:
        """
        進場買入流程。

        步驟：
        1. 查詢帳戶 NetLiquidation
        2. 查詢目前 TQQQ 持倉
        3. 取得 TQQQ 最新市價
        4. 計算目標股數 = floor(NetLiquidation × USE_EQUITY_PCT ÷ 市價)
        5. 差值 > 0 時下市價買單；差值 ≤ 0 時跳過

        Args:
            signal: 已驗證的交易訊號

        Returns:
            OrderResult 訂單執行結果
        """
        ticker = signal.ticker

        try:
            # 步驟 1：查詢帳戶淨資產
            net_liquidation = self._get_net_liquidation()
            logger.info("帳戶 NetLiquidation: %.2f", net_liquidation)

            # 步驟 2：查詢目前持倉
            current_position = self._get_position(ticker)
            logger.info("目前 %s 持倉: %d 股", ticker, current_position)

            # 步驟 3：取得最新市價
            market_price = self._get_market_price(ticker)
            logger.info("%s 最新市價: %.4f", ticker, market_price)

            # 步驟 4：計算目標股數
            target_shares = self.calculate_target_shares(
                net_liquidation, market_price, self._config.use_equity_pct
            )
            logger.info(
                "目標股數計算: floor(%.2f × %.4f ÷ %.4f) = %d",
                net_liquidation, self._config.use_equity_pct, market_price, target_shares,
            )

            # 步驟 5：計算需買入股數
            shares_to_buy = target_shares - current_position
            logger.info("需買入股數: %d (目標 %d - 持倉 %d)", shares_to_buy, target_shares, current_position)

            # 差值 ≤ 0 時跳過下單
            if shares_to_buy <= 0:
                msg = f"無需額外買入：目標 {target_shares} 股 ≤ 目前持倉 {current_position} 股"
                logger.info(msg)
                return OrderResult(
                    success=True,
                    action="skip",
                    ticker=ticker,
                    shares=0,
                    order_id=None,
                    message=msg,
                    net_liquidation=net_liquidation,
                    market_price=market_price,
                    target_shares=target_shares,
                )

            # 步驟 6：提交市價買單
            contract = Stock(ticker, "SMART", "USD")
            order = MarketOrder("BUY", shares_to_buy)
            trade = self._ib.placeOrder(contract, order)
            order_id = trade.order.orderId

            logger.info(
                "已提交市價買單: %s BUY %d 股, orderId=%s",
                ticker, shares_to_buy, order_id,
            )

            # 發送交易通知
            self._notifier.send_trade_notification(
                direction="買入",
                ticker=ticker,
                shares=shares_to_buy,
                price=market_price,
            )

            return OrderResult(
                success=True,
                action="entry",
                ticker=ticker,
                shares=shares_to_buy,
                order_id=order_id,
                message=f"已提交買單: {shares_to_buy} 股",
                net_liquidation=net_liquidation,
                market_price=market_price,
                target_shares=target_shares,
            )

        except Exception as e:
            logger.exception("進場買入流程發生錯誤")
            self._notifier.send_error_notification(
                error_type="進場買入失敗",
                description=str(e),
            )
            return OrderResult(
                success=False,
                action="entry",
                ticker=ticker,
                shares=0,
                order_id=None,
                message=f"進場失敗: {e}",
                net_liquidation=None,
                market_price=None,
                target_shares=None,
            )

    def handle_close(self, signal: SignalPayload) -> OrderResult:
        """
        出場平倉流程。

        步驟：
        1. 查詢目前 TQQQ 持倉
        2. 持倉 > 0 時下市價賣單全部平倉
        3. 持倉 = 0 時跳過

        Args:
            signal: 已驗證的交易訊號

        Returns:
            OrderResult 訂單執行結果
        """
        ticker = signal.ticker

        try:
            # 步驟 1：查詢目前持倉
            current_position = self._get_position(ticker)
            logger.info("目前 %s 持倉: %d 股", ticker, current_position)

            # 持倉為 0 時跳過平倉
            if current_position <= 0:
                msg = "目前無持倉，無需平倉"
                logger.info(msg)
                return OrderResult(
                    success=True,
                    action="skip",
                    ticker=ticker,
                    shares=0,
                    order_id=None,
                    message=msg,
                    net_liquidation=None,
                    market_price=None,
                    target_shares=None,
                )

            # 步驟 2：提交市價賣單（全部持倉）
            contract = Stock(ticker, "SMART", "USD")
            order = MarketOrder("SELL", current_position)
            trade = self._ib.placeOrder(contract, order)
            order_id = trade.order.orderId

            # 取得市價用於通知（非必要，失敗不影響主流程）
            try:
                market_price = self._get_market_price(ticker)
            except Exception:
                market_price = 0.0

            logger.info(
                "已提交市價賣單: %s SELL %d 股, orderId=%s",
                ticker, current_position, order_id,
            )

            # 發送交易通知
            self._notifier.send_trade_notification(
                direction="賣出",
                ticker=ticker,
                shares=current_position,
                price=market_price,
            )

            return OrderResult(
                success=True,
                action="close",
                ticker=ticker,
                shares=current_position,
                order_id=order_id,
                message=f"已提交賣單: {current_position} 股",
                net_liquidation=None,
                market_price=market_price,
                target_shares=None,
            )

        except Exception as e:
            logger.exception("出場平倉流程發生錯誤")
            self._notifier.send_error_notification(
                error_type="出場平倉失敗",
                description=str(e),
            )
            return OrderResult(
                success=False,
                action="close",
                ticker=ticker,
                shares=0,
                order_id=None,
                message=f"平倉失敗: {e}",
                net_liquidation=None,
                market_price=None,
                target_shares=None,
            )

    # ------------------------------------------------------------------
    # 私有輔助方法
    # ------------------------------------------------------------------

    def _get_net_liquidation(self) -> float:
        """
        查詢帳戶 NetLiquidation 值。

        透過 ib.accountSummary() 取得帳戶摘要，
        篩選 tag 為 "NetLiquidation" 的項目。

        Returns:
            帳戶淨資產值

        Raises:
            RuntimeError: 無法取得 NetLiquidation
        """
        summary = self._ib.accountSummary()
        for item in summary:
            if item.tag == "NetLiquidation":
                value = float(item.value)
                logger.debug("取得 NetLiquidation: %.2f (account=%s)", value, item.account)
                return value

        raise RuntimeError("無法從帳戶摘要中取得 NetLiquidation")

    def _get_position(self, ticker: str) -> int:
        """
        查詢指定標的的持倉數量。

        透過 ib.positions() 取得所有持倉，
        篩選 symbol 符合的項目。

        Args:
            ticker: 標的代碼（例如 "TQQQ"）

        Returns:
            持倉股數（無持倉時回傳 0）
        """
        positions = self._ib.positions()
        for pos in positions:
            if pos.contract.symbol == ticker:
                shares = int(pos.position)
                logger.debug("取得 %s 持倉: %d 股", ticker, shares)
                return shares

        logger.debug("%s 無持倉", ticker)
        return 0

    def _get_market_price(self, ticker: str) -> float:
        """
        取得指定標的的最新市價。

        透過 ib.reqTickers() 取得即時報價。

        Args:
            ticker: 標的代碼（例如 "TQQQ"）

        Returns:
            最新市價

        Raises:
            RuntimeError: 無法取得有效市價
        """
        contract = Stock(ticker, "SMART", "USD")
        self._ib.qualifyContracts(contract)
        tickers = self._ib.reqTickers(contract)

        if tickers:
            tick = tickers[0]
            # 優先使用 last price，其次 close price
            price = tick.last if tick.last and tick.last > 0 else tick.close
            if price and price > 0:
                logger.debug("取得 %s 市價: %.4f", ticker, price)
                return float(price)

        raise RuntimeError(f"無法取得 {ticker} 的有效市價")
