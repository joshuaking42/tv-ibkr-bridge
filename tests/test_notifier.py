# Notifier 通知模組單元測試

from unittest.mock import MagicMock, patch

import pytest

from app.config import Config
from app.notifier import Notifier


def _make_config(webhook_url=None):
    """建立測試用 Config，僅設定 discord_webhook_url。"""
    return Config(
        webhook_token="test",
        ib_host="127.0.0.1",
        ib_port=4002,
        ib_client_id=1,
        discord_webhook_url=webhook_url,
    )


class TestSendDiscord:
    """_send_discord 底層方法測試"""

    def test_skip_when_url_is_none(self):
        """DISCORD_WEBHOOK_URL 為 None 時靜默跳過，不發送請求"""
        notifier = Notifier(_make_config(webhook_url=None))
        # 不應呼叫 requests.post
        with patch("app.notifier.requests.post") as mock_post:
            result = notifier._send_discord("test")
            mock_post.assert_not_called()
            assert result is False

    @patch("app.notifier.requests.post")
    def test_success(self, mock_post):
        """成功發送時回傳 True，且 payload 格式正確"""
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier(_make_config(webhook_url="https://discord.com/api/webhooks/test"))
        result = notifier._send_discord("hello")

        assert result is True
        mock_post.assert_called_once_with(
            "https://discord.com/api/webhooks/test",
            json={"content": "hello"},
            timeout=10,
        )

    @patch("app.notifier.requests.post", side_effect=Exception("network error"))
    def test_failure_logs_and_returns_false(self, mock_post):
        """發送失敗時記錄日誌、回傳 False，不拋出例外"""
        notifier = Notifier(_make_config(webhook_url="https://discord.com/api/webhooks/test"))
        result = notifier._send_discord("hello")
        assert result is False


class TestSendTradeNotification:
    """send_trade_notification 測試"""

    @patch("app.notifier.requests.post")
    def test_message_contains_required_fields(self, mock_post):
        """交易通知訊息應包含方向、標的、股數、價格"""
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier(_make_config(webhook_url="https://discord.com/api/webhooks/test"))
        notifier.send_trade_notification("BUY", "TQQQ", 100, 65.5)

        call_args = mock_post.call_args
        content = call_args.kwargs["json"]["content"]
        assert "BUY" in content
        assert "TQQQ" in content
        assert "100" in content
        assert "65.5" in content


class TestSendErrorNotification:
    """send_error_notification 測試"""

    @patch("app.notifier.requests.post")
    def test_message_contains_error_info(self, mock_post):
        """錯誤通知訊息應包含錯誤類型與描述"""
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        notifier = Notifier(_make_config(webhook_url="https://discord.com/api/webhooks/test"))
        notifier.send_error_notification("ConnectionError", "IB Gateway 斷線")

        call_args = mock_post.call_args
        content = call_args.kwargs["json"]["content"]
        assert "ConnectionError" in content
        assert "IB Gateway 斷線" in content
