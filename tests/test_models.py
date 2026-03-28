"""SignalPayload 與 OrderResult 資料模型的單元測試"""

import pytest

from app.models import OrderResult, SignalPayload, VALID_ACTIONS


class TestSignalPayloadFromDict:
    """測試 SignalPayload.from_dict() 類別方法"""

    def test_full_payload(self):
        """所有欄位皆提供時，應正確解析"""
        data = {
            "action": "entry",
            "ticker": "TQQQ",
            "direction": "long",
            "quantity_pct": 1.0,
            "price": 65.50,
            "timestamp": 1700000000,
            "signal_score": 0.85,
            "strategy_id": "tv-macd-cross",
        }
        signal = SignalPayload.from_dict(data)
        assert signal.action == "entry"
        assert signal.ticker == "TQQQ"
        assert signal.direction == "long"
        assert signal.quantity_pct == 1.0
        assert signal.price == 65.50
        assert signal.timestamp == 1700000000
        assert signal.signal_score == 0.85
        assert signal.strategy_id == "tv-macd-cross"

    def test_minimal_payload_defaults(self):
        """僅提供必要欄位時，選用欄位應使用預設值"""
        data = {"action": "close", "ticker": "TQQQ"}
        signal = SignalPayload.from_dict(data)
        assert signal.action == "close"
        assert signal.ticker == "TQQQ"
        assert signal.direction == "long"
        assert signal.quantity_pct == 100.0
        assert signal.price == 0.0
        assert signal.timestamp == 0
        assert signal.signal_score == 0.0
        assert signal.strategy_id == ""

    def test_missing_action_raises(self):
        """缺少 action 欄位時應拋出 ValueError"""
        with pytest.raises(ValueError, match="action"):
            SignalPayload.from_dict({"ticker": "TQQQ"})

    def test_missing_ticker_raises(self):
        """缺少 ticker 欄位時應拋出 ValueError"""
        with pytest.raises(ValueError, match="ticker"):
            SignalPayload.from_dict({"action": "entry"})

    def test_invalid_action_raises(self):
        """action 值不為 entry/close 時應拋出 ValueError"""
        with pytest.raises(ValueError, match="不支援的 action 類型"):
            SignalPayload.from_dict({"action": "buy", "ticker": "TQQQ"})

    def test_empty_dict_raises(self):
        """空 dict 應拋出 ValueError（缺少 action）"""
        with pytest.raises(ValueError, match="action"):
            SignalPayload.from_dict({})

    def test_close_action(self):
        """action 為 close 時應正確解析"""
        signal = SignalPayload.from_dict({"action": "close", "ticker": "TQQQ"})
        assert signal.action == "close"


class TestOrderResult:
    """測試 OrderResult dataclass"""

    def test_create_success_result(self):
        """應能建立成功的訂單結果"""
        result = OrderResult(
            success=True,
            action="entry",
            ticker="TQQQ",
            shares=100,
            order_id=12345,
            message="買入成功",
            net_liquidation=50000.0,
            market_price=65.50,
            target_shares=100,
        )
        assert result.success is True
        assert result.shares == 100
        assert result.order_id == 12345

    def test_create_skip_result(self):
        """應能建立跳過下單的結果（含 None 欄位）"""
        result = OrderResult(
            success=True,
            action="skip",
            ticker="TQQQ",
            shares=0,
            order_id=None,
            message="無需額外買入",
            net_liquidation=None,
            market_price=None,
            target_shares=None,
        )
        assert result.success is True
        assert result.order_id is None
        assert result.shares == 0
