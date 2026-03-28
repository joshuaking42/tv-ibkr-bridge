# Config 資料類別單元測試

import os
import pytest
from app.config import Config


@pytest.fixture
def full_env(monkeypatch):
    """設定所有必要環境變數。"""
    monkeypatch.setenv("WEBHOOK_TOKEN", "test-secret-token")
    monkeypatch.setenv("IB_HOST", "127.0.0.1")
    monkeypatch.setenv("IB_PORT", "4002")
    monkeypatch.setenv("IB_CLIENT_ID", "1")


class TestConfigFromEnv:
    """測試 Config.from_env() 類別方法。"""

    def test_loads_all_required_vars(self, full_env):
        """必要環境變數皆存在時，正確載入所有值。"""
        cfg = Config.from_env()
        assert cfg.webhook_token == "test-secret-token"
        assert cfg.ib_host == "127.0.0.1"
        assert cfg.ib_port == 4002
        assert cfg.ib_client_id == 1

    def test_default_use_equity_pct(self, full_env):
        """USE_EQUITY_PCT 未設定時預設為 0.95。"""
        cfg = Config.from_env()
        assert cfg.use_equity_pct == 0.95

    def test_custom_use_equity_pct(self, full_env, monkeypatch):
        """USE_EQUITY_PCT 設定時正確載入自訂值。"""
        monkeypatch.setenv("USE_EQUITY_PCT", "0.80")
        cfg = Config.from_env()
        assert cfg.use_equity_pct == 0.80

    def test_default_discord_webhook_url_is_none(self, full_env):
        """DISCORD_WEBHOOK_URL 未設定時預設為 None。"""
        cfg = Config.from_env()
        assert cfg.discord_webhook_url is None

    def test_custom_discord_webhook_url(self, full_env, monkeypatch):
        """DISCORD_WEBHOOK_URL 設定時正確載入。"""
        url = "https://discord.com/api/webhooks/123/abc"
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", url)
        cfg = Config.from_env()
        assert cfg.discord_webhook_url == url

    def test_missing_single_required_var(self, monkeypatch):
        """缺少單一必要變數時拋出 ValueError，訊息包含變數名稱。"""
        monkeypatch.setenv("IB_HOST", "127.0.0.1")
        monkeypatch.setenv("IB_PORT", "4002")
        monkeypatch.setenv("IB_CLIENT_ID", "1")
        # 未設定 WEBHOOK_TOKEN
        monkeypatch.delenv("WEBHOOK_TOKEN", raising=False)

        with pytest.raises(ValueError, match="WEBHOOK_TOKEN"):
            Config.from_env()

    def test_missing_multiple_required_vars(self, monkeypatch):
        """缺少多個必要變數時，錯誤訊息包含所有缺少的變數名稱。"""
        # 清除所有必要變數
        for var in ["WEBHOOK_TOKEN", "IB_HOST", "IB_PORT", "IB_CLIENT_ID"]:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(ValueError) as exc_info:
            Config.from_env()

        error_msg = str(exc_info.value)
        assert "WEBHOOK_TOKEN" in error_msg
        assert "IB_HOST" in error_msg
        assert "IB_PORT" in error_msg
        assert "IB_CLIENT_ID" in error_msg

    def test_ib_port_parsed_as_int(self, full_env):
        """IB_PORT 環境變數字串正確轉換為 int。"""
        cfg = Config.from_env()
        assert isinstance(cfg.ib_port, int)

    def test_ib_client_id_parsed_as_int(self, full_env):
        """IB_CLIENT_ID 環境變數字串正確轉換為 int。"""
        cfg = Config.from_env()
        assert isinstance(cfg.ib_client_id, int)
