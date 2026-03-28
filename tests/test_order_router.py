# OrderRouter 單元測試
# 驗證目標股數計算、進場買入、出場平倉等核心邏輯

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.config import Config
from app.models import OrderResult, SignalPayload
from app.order_router import OrderRouter


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_config() -> Config:
    """建立測試用 Config，use_equity_pct = 0.95"""
    return Config(
        webhook_token="test-token",
        ib_host="127.0.0.1",
        ib_port=4002,
        ib_client_id=1,
        use_equity_pct=0.95,
        discord_webhook_url=None,
    )


@pytest.fixture
def mock_ib() -> MagicMock:
    """建立 mock IB 實例"""
    return MagicMock()


@pytest.fixture
def mock_notifier() -> MagicMock:
    """建立 mock Notifier"""
    return MagicMock()


@pytest.fixture
def router(mock_ib: MagicMock, mock_config: Config, mock_notifier: MagicMock) -> OrderRouter:
    """建立 OrderRouter 實例"""
    return OrderRouter(ib=mock_ib, config=mock_config, notifier=mock_notifier)


@pytest.fixture
def entry_signal() -> SignalPayload:
    """建立進場訊號"""
    return SignalPayload.from_dict({"action": "entry", "ticker": "TQQQ"})


@pytest.fixture
def close_signal() -> SignalPayload:
    """建立平倉訊號"""
    return SignalPayload.from_dict({"action": "close", "ticker": "TQQQ"})


# ------------------------------------------------------------------
# calculate_target_shares 測試
# ------------------------------------------------------------------


class TestCalculateTargetShares:
    """測試目標股數計算公式：floor(NetLiquidation × USE_EQUITY_PCT ÷ 市價)"""

    def test_basic_calculation(self, router: OrderRouter) -> None:
        """基本計算：100000 × 0.95 ÷ 65.50 = floor(1450.38) = 1450"""
        result = router.calculate_target_shares(100_000.0, 65.50, 0.95)
        expected = math.floor(100_000.0 * 0.95 / 65.50)
        assert result == expected

    def test_result_is_integer(self, router: OrderRouter) -> None:
        """結果必為整數"""
        result = router.calculate_target_shares(50_000.0, 33.33, 0.90)
        assert isinstance(result, int)

    def test_result_is_non_negative(self, router: OrderRouter) -> None:
        """結果必為非負"""
        result = router.calculate_target_shares(0.0, 100.0, 0.95)
        assert result >= 0

    def test_zero_market_price_returns_zero(self, router: OrderRouter) -> None:
        """市價為 0 時回傳 0（避免除以零）"""
        result = router.calculate_target_shares(100_000.0, 0.0, 0.95)
        assert result == 0

    def test_negative_market_price_returns_zero(self, router: OrderRouter) -> None:
        """市價為負數時回傳 0"""
        result = router.calculate_target_shares(100_000.0, -10.0, 0.95)
        assert result == 0

    def test_small_account_high_price(self, router: OrderRouter) -> None:
        """小帳戶高股價：1000 × 0.95 ÷ 500 = floor(1.9) = 1"""
        result = router.calculate_target_shares(1_000.0, 500.0, 0.95)
        assert result == 1

    def test_exact_division(self, router: OrderRouter) -> None:
        """整除情況：10000 × 1.0 ÷ 100 = 100"""
        result = router.calculate_target_shares(10_000.0, 100.0, 1.0)
        assert result == 100


# ------------------------------------------------------------------
# handle_entry 測試
# ------------------------------------------------------------------


def _make_account_summary_item(tag: str, value: str, account: str = "DU123456"):
    """建立模擬的 accountSummary 項目"""
    return SimpleNamespace(tag=tag, value=value, account=account)


def _make_position(symbol: str, position: float):
    """建立模擬的 position 項目"""
    contract = SimpleNamespace(symbol=symbol)
    return SimpleNamespace(contract=contract, position=position)


def _make_ticker(last: float, close: float = 0.0):
    """建立模擬的 ticker 項目"""
    return SimpleNamespace(last=last, close=close)


class TestHandleEntry:
    """測試進場買入流程"""

    def test_entry_places_buy_order(
        self, router: OrderRouter, mock_ib: MagicMock, mock_notifier: MagicMock, entry_signal: SignalPayload
    ) -> None:
        """目標 > 持倉時應下市價買單"""
        # 設定 mock：NetLiquidation=100000, 持倉=0, 市價=65.50
        mock_ib.accountSummary.return_value = [
            _make_account_summary_item("NetLiquidation", "100000"),
        ]
        mock_ib.positions.return_value = []
        mock_ib.reqTickers.return_value = [_make_ticker(last=65.50)]

        # 模擬下單回傳
        mock_trade = MagicMock()
        mock_trade.order.orderId = 42
        mock_ib.placeOrder.return_value = mock_trade

        result = router.handle_entry(entry_signal)

        # 驗證結果
        expected_shares = math.floor(100_000 * 0.95 / 65.50)
        assert result.success is True
        assert result.action == "entry"
        assert result.shares == expected_shares
        assert result.order_id == 42

        # 驗證下單呼叫
        mock_ib.placeOrder.assert_called_once()

        # 驗證通知
        mock_notifier.send_trade_notification.assert_called_once()

    def test_entry_skips_when_target_le_position(
        self, router: OrderRouter, mock_ib: MagicMock, mock_notifier: MagicMock, entry_signal: SignalPayload
    ) -> None:
        """目標 ≤ 持倉時跳過下單"""
        # 設定 mock：NetLiquidation=100000, 持倉=2000, 市價=65.50
        # 目標 = floor(100000 * 0.95 / 65.50) = 1450 < 2000
        mock_ib.accountSummary.return_value = [
            _make_account_summary_item("NetLiquidation", "100000"),
        ]
        mock_ib.positions.return_value = [_make_position("TQQQ", 2000)]
        mock_ib.reqTickers.return_value = [_make_ticker(last=65.50)]

        result = router.handle_entry(entry_signal)

        assert result.success is True
        assert result.action == "skip"
        assert result.shares == 0
        # 不應下單
        mock_ib.placeOrder.assert_not_called()
        # 不應發送交易通知
        mock_notifier.send_trade_notification.assert_not_called()

    def test_entry_buys_difference_when_partial_position(
        self, router: OrderRouter, mock_ib: MagicMock, entry_signal: SignalPayload
    ) -> None:
        """已有部分持倉時，只買入差額"""
        # 目標 = floor(100000 * 0.95 / 50) = 1900, 持倉 = 500, 差額 = 1400
        mock_ib.accountSummary.return_value = [
            _make_account_summary_item("NetLiquidation", "100000"),
        ]
        mock_ib.positions.return_value = [_make_position("TQQQ", 500)]
        mock_ib.reqTickers.return_value = [_make_ticker(last=50.0)]

        mock_trade = MagicMock()
        mock_trade.order.orderId = 99
        mock_ib.placeOrder.return_value = mock_trade

        result = router.handle_entry(entry_signal)

        expected_target = math.floor(100_000 * 0.95 / 50.0)
        expected_buy = expected_target - 500
        assert result.shares == expected_buy
        assert result.success is True

    def test_entry_error_sends_notification(
        self, router: OrderRouter, mock_ib: MagicMock, mock_notifier: MagicMock, entry_signal: SignalPayload
    ) -> None:
        """進場發生錯誤時發送錯誤通知"""
        mock_ib.accountSummary.side_effect = RuntimeError("連線中斷")

        result = router.handle_entry(entry_signal)

        assert result.success is False
        mock_notifier.send_error_notification.assert_called_once()


# ------------------------------------------------------------------
# handle_close 測試
# ------------------------------------------------------------------


class TestHandleClose:
    """測試出場平倉流程"""

    def test_close_sells_all_position(
        self, router: OrderRouter, mock_ib: MagicMock, mock_notifier: MagicMock, close_signal: SignalPayload
    ) -> None:
        """持倉 > 0 時應下市價賣單全部平倉"""
        mock_ib.positions.return_value = [_make_position("TQQQ", 1500)]
        mock_ib.reqTickers.return_value = [_make_ticker(last=70.0)]

        mock_trade = MagicMock()
        mock_trade.order.orderId = 55
        mock_ib.placeOrder.return_value = mock_trade

        result = router.handle_close(close_signal)

        assert result.success is True
        assert result.action == "close"
        assert result.shares == 1500
        assert result.order_id == 55

        # 驗證通知
        mock_notifier.send_trade_notification.assert_called_once()

    def test_close_skips_when_no_position(
        self, router: OrderRouter, mock_ib: MagicMock, mock_notifier: MagicMock, close_signal: SignalPayload
    ) -> None:
        """持倉為 0 時跳過平倉"""
        mock_ib.positions.return_value = []

        result = router.handle_close(close_signal)

        assert result.success is True
        assert result.action == "skip"
        assert result.shares == 0
        assert "無持倉" in result.message
        # 不應下單
        mock_ib.placeOrder.assert_not_called()
        # 不應發送交易通知
        mock_notifier.send_trade_notification.assert_not_called()

    def test_close_error_sends_notification(
        self, router: OrderRouter, mock_ib: MagicMock, mock_notifier: MagicMock, close_signal: SignalPayload
    ) -> None:
        """平倉發生錯誤時發送錯誤通知"""
        mock_ib.positions.side_effect = RuntimeError("連線中斷")

        result = router.handle_close(close_signal)

        assert result.success is False
        mock_notifier.send_error_notification.assert_called_once()

    def test_close_logs_calculation(
        self, router: OrderRouter, mock_ib: MagicMock, close_signal: SignalPayload
    ) -> None:
        """平倉時記錄持倉資訊"""
        mock_ib.positions.return_value = [_make_position("TQQQ", 800)]
        mock_ib.reqTickers.return_value = [_make_ticker(last=60.0)]

        mock_trade = MagicMock()
        mock_trade.order.orderId = 77
        mock_ib.placeOrder.return_value = mock_trade

        result = router.handle_close(close_signal)

        assert result.shares == 800
        assert result.success is True
