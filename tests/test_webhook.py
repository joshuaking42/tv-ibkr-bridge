# Webhook 端點單元測試

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock

import pytest

from app.config import Config
from app.models import OrderResult
from app.webhook import create_app


@pytest.fixture
def config():
    """建立測試用 Config。"""
    return Config(
        webhook_token="test-secret-token",
        ib_host="127.0.0.1",
        ib_port=4002,
        ib_client_id=1,
        use_equity_pct=0.95,
        discord_webhook_url=None,
    )


@pytest.fixture
def ib_manager():
    """建立 mock IBManager。"""
    mgr = MagicMock()
    mgr.is_connected = True
    mgr.ensure_connected.return_value = True
    return mgr


@pytest.fixture
def order_router():
    """建立 mock OrderRouter。"""
    return MagicMock()


@pytest.fixture
def notifier():
    """建立 mock Notifier。"""
    return MagicMock()


@pytest.fixture
def client(config, ib_manager, order_router, notifier):
    """建立 Flask test client。"""
    app = create_app(config, ib_manager, order_router, notifier)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _valid_payload():
    """回傳合法的 Signal_Payload dict。"""
    return {
        "action": "entry",
        "ticker": "TQQQ",
        "direction": "long",
        "quantity_pct": 1.0,
        "price": 65.50,
        "timestamp": 1700000000,
        "signal_score": 0.85,
        "strategy_id": "tv-macd-cross",
    }


def _success_order_result():
    """回傳成功的 OrderResult。"""
    return OrderResult(
        success=True,
        action="entry",
        ticker="TQQQ",
        shares=100,
        order_id=12345,
        message="已提交買單: 100 股",
        net_liquidation=50000.0,
        market_price=65.50,
        target_shares=726,
    )


# --- Token 驗證測試 ---

class TestTokenValidation:
    """Token 驗證相關測試。"""

    def test_missing_token_returns_403(self, client):
        """缺少 token 參數時回傳 403。"""
        resp = client.post("/webhook", json=_valid_payload())
        assert resp.status_code == 403

    def test_wrong_token_returns_403(self, client):
        """token 不正確時回傳 403。"""
        resp = client.post("/webhook?token=wrong-token", json=_valid_payload())
        assert resp.status_code == 403

    def test_empty_token_returns_403(self, client):
        """空字串 token 回傳 403。"""
        resp = client.post("/webhook?token=", json=_valid_payload())
        assert resp.status_code == 403

    def test_valid_token_passes(self, client, order_router):
        """正確 token 通過驗證，進入後續處理。"""
        order_router.handle_entry.return_value = _success_order_result()
        resp = client.post(
            "/webhook?token=test-secret-token",
            json=_valid_payload(),
        )
        assert resp.status_code == 200


# --- JSON 解析測試 ---

class TestPayloadParsing:
    """JSON body 解析相關測試。"""

    def test_invalid_json_returns_400(self, client):
        """無效 JSON 格式回傳 400。"""
        resp = client.post(
            "/webhook?token=test-secret-token",
            data="not-json{{{",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_missing_action_returns_400(self, client):
        """缺少 action 欄位回傳 400。"""
        payload = {"ticker": "TQQQ"}
        resp = client.post("/webhook?token=test-secret-token", json=payload)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "action" in data["message"]

    def test_missing_ticker_returns_400(self, client):
        """缺少 ticker 欄位回傳 400。"""
        payload = {"action": "entry"}
        resp = client.post("/webhook?token=test-secret-token", json=payload)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "ticker" in data["message"]

    def test_unsupported_action_returns_400(self, client):
        """不支援的 action 類型回傳 400。"""
        payload = {"action": "unknown", "ticker": "TQQQ"}
        resp = client.post("/webhook?token=test-secret-token", json=payload)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "不支援" in data["message"]


# --- IB Gateway 連線測試 ---

class TestIBConnection:
    """IB Gateway 連線狀態測試。"""

    def test_disconnected_returns_503(self, client, ib_manager):
        """IB Gateway 斷線時回傳 503。"""
        ib_manager.ensure_connected.return_value = False
        resp = client.post(
            "/webhook?token=test-secret-token",
            json=_valid_payload(),
        )
        assert resp.status_code == 503
        data = resp.get_json()
        assert "連線中斷" in data["message"]


# --- 訂單路由測試 ---

class TestOrderRouting:
    """訂單路由相關測試。"""

    def test_entry_action_calls_handle_entry(self, client, order_router):
        """action=entry 時呼叫 handle_entry。"""
        order_router.handle_entry.return_value = _success_order_result()
        payload = _valid_payload()
        payload["action"] = "entry"
        resp = client.post("/webhook?token=test-secret-token", json=payload)
        assert resp.status_code == 200
        order_router.handle_entry.assert_called_once()

    def test_close_action_calls_handle_close(self, client, order_router):
        """action=close 時呼叫 handle_close。"""
        close_result = OrderResult(
            success=True,
            action="close",
            ticker="TQQQ",
            shares=100,
            order_id=12346,
            message="已提交賣單: 100 股",
            net_liquidation=None,
            market_price=65.50,
            target_shares=None,
        )
        order_router.handle_close.return_value = close_result
        payload = _valid_payload()
        payload["action"] = "close"
        resp = client.post("/webhook?token=test-secret-token", json=payload)
        assert resp.status_code == 200
        order_router.handle_close.assert_called_once()

    def test_response_contains_order_result(self, client, order_router):
        """回應 body 包含 OrderResult 欄位。"""
        order_router.handle_entry.return_value = _success_order_result()
        resp = client.post(
            "/webhook?token=test-secret-token",
            json=_valid_payload(),
        )
        data = resp.get_json()
        assert data["success"] is True
        assert data["ticker"] == "TQQQ"
        assert data["shares"] == 100
        assert data["order_id"] == 12345


# --- HTTP 方法測試 ---

class TestHTTPMethods:
    """HTTP 方法限制測試。"""

    def test_get_returns_405(self, client):
        """GET 請求回傳 405 Method Not Allowed。"""
        resp = client.get("/webhook?token=test-secret-token")
        assert resp.status_code == 405
