# IBManager 單元測試
# 驗證連線管理、自動重連與通知行為

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ib_manager import IBManager, DEFAULT_TIMEOUT, MAX_RETRIES


@pytest.fixture
def notifier():
    """建立 mock Notifier。"""
    return MagicMock()


@pytest.fixture
def manager(notifier):
    """建立 IBManager 實例，使用 mock 的 IB 連線。"""
    with patch("app.ib_manager.IB") as MockIB:
        mock_ib_instance = MagicMock()
        MockIB.return_value = mock_ib_instance
        mgr = IBManager(host="127.0.0.1", port=4002, client_id=1, notifier=notifier)
    return mgr


class TestConnect:
    """測試 connect() 方法。"""

    def test_connect_success(self, manager):
        """連線成功時回傳 True。"""
        manager._ib.connect.return_value = None
        assert manager.connect() is True
        manager._ib.connect.assert_called_once_with(
            host="127.0.0.1", port=4002, clientId=1, timeout=DEFAULT_TIMEOUT,
        )

    def test_connect_failure(self, manager):
        """連線失敗時回傳 False。"""
        manager._ib.connect.side_effect = ConnectionError("refused")
        assert manager.connect() is False

    def test_connect_custom_timeout(self, manager):
        """可自訂連線逾時秒數。"""
        manager._ib.connect.return_value = None
        manager.connect(timeout=10)
        manager._ib.connect.assert_called_once_with(
            host="127.0.0.1", port=4002, clientId=1, timeout=10,
        )


class TestIsConnected:
    """測試 is_connected property。"""

    def test_connected(self, manager):
        """已連線時回傳 True。"""
        manager._ib.isConnected.return_value = True
        assert manager.is_connected is True

    def test_disconnected(self, manager):
        """未連線時回傳 False。"""
        manager._ib.isConnected.return_value = False
        assert manager.is_connected is False


class TestEnsureConnected:
    """測試 ensure_connected() 方法。"""

    def test_already_connected(self, manager):
        """已連線時直接回傳 True，不嘗試重連。"""
        manager._ib.isConnected.return_value = True
        assert manager.ensure_connected() is True
        manager._ib.connect.assert_not_called()

    @patch("app.ib_manager.time.sleep")
    def test_reconnect_first_attempt(self, mock_sleep, manager):
        """斷線後第一次重連成功。"""
        manager._ib.isConnected.return_value = False
        manager._ib.connect.return_value = None  # 連線成功
        assert manager.ensure_connected() is True
        assert manager._ib.connect.call_count == 1
        mock_sleep.assert_not_called()

    @patch("app.ib_manager.time.sleep")
    def test_reconnect_second_attempt(self, mock_sleep, manager, notifier):
        """第一次失敗、第二次成功。"""
        manager._ib.isConnected.return_value = False
        manager._ib.connect.side_effect = [
            ConnectionError("fail"),  # 第 1 次失敗
            None,                     # 第 2 次成功
        ]
        assert manager.ensure_connected() is True
        assert manager._ib.connect.call_count == 2
        mock_sleep.assert_called_once_with(5)
        notifier.send_error_notification.assert_not_called()

    @patch("app.ib_manager.time.sleep")
    def test_all_retries_failed(self, mock_sleep, manager, notifier):
        """重連 3 次全部失敗，發送錯誤通知。"""
        manager._ib.isConnected.return_value = False
        manager._ib.connect.side_effect = ConnectionError("refused")
        assert manager.ensure_connected() is False
        assert manager._ib.connect.call_count == MAX_RETRIES
        # 前兩次失敗後各等待 5 秒，第三次失敗後不等待
        assert mock_sleep.call_count == MAX_RETRIES - 1
        notifier.send_error_notification.assert_called_once()
        call_kwargs = notifier.send_error_notification.call_args
        assert "連線失敗" in call_kwargs.kwargs.get("error_type", call_kwargs[1].get("error_type", str(call_kwargs)))

    @patch("app.ib_manager.time.sleep")
    def test_third_attempt_success(self, mock_sleep, manager, notifier):
        """前兩次失敗、第三次成功。"""
        manager._ib.isConnected.return_value = False
        manager._ib.connect.side_effect = [
            ConnectionError("fail"),  # 第 1 次
            ConnectionError("fail"),  # 第 2 次
            None,                     # 第 3 次成功
        ]
        assert manager.ensure_connected() is True
        assert manager._ib.connect.call_count == 3
        assert mock_sleep.call_count == 2
        notifier.send_error_notification.assert_not_called()


class TestIBProperty:
    """測試 ib property。"""

    def test_ib_returns_instance(self, manager):
        """ib property 回傳底層 IB 實例。"""
        assert manager.ib is manager._ib
