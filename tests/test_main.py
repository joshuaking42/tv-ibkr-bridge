# main.py 入口模組測試

import logging
from unittest.mock import MagicMock, patch

import pytest


class TestMain:
    """測試 main() 函式的初始化與錯誤處理流程。"""

    @patch("main.Config")
    @patch("main.Notifier")
    @patch("main.IBManager")
    @patch("main.OrderRouter")
    @patch("main.create_app")
    def test_successful_startup(
        self, mock_create_app, mock_order_router_cls, mock_ib_manager_cls,
        mock_notifier_cls, mock_config_cls,
    ):
        """正常啟動：所有元件初始化成功，Flask app.run 被呼叫。"""
        from main import main

        # 設定 mock
        mock_config = MagicMock()
        mock_config.ib_host = "127.0.0.1"
        mock_config.ib_port = 4002
        mock_config.ib_client_id = 1
        mock_config_cls.from_env.return_value = mock_config

        mock_notifier = MagicMock()
        mock_notifier_cls.return_value = mock_notifier

        mock_ib_manager = MagicMock()
        mock_ib_manager.connect.return_value = True
        mock_ib_manager.ib = MagicMock()
        mock_ib_manager_cls.return_value = mock_ib_manager

        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        # 執行
        main()

        # 驗證
        mock_config_cls.from_env.assert_called_once()
        mock_notifier_cls.assert_called_once_with(mock_config)
        mock_ib_manager_cls.assert_called_once_with(
            host="127.0.0.1", port=4002, client_id=1, notifier=mock_notifier,
        )
        mock_ib_manager.connect.assert_called_once()
        mock_order_router_cls.assert_called_once_with(
            ib=mock_ib_manager.ib, config=mock_config, notifier=mock_notifier,
        )
        mock_create_app.assert_called_once()
        mock_app.run.assert_called_once_with(host="0.0.0.0", port=5000)

    @patch("main.Config")
    def test_missing_env_vars_exits(self, mock_config_cls):
        """缺少必要環境變數時，應以 exit code 1 終止。"""
        from main import main

        mock_config_cls.from_env.side_effect = ValueError("缺少必要環境變數: WEBHOOK_TOKEN")

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("main.Config")
    @patch("main.Notifier")
    @patch("main.IBManager")
    @patch("main.OrderRouter")
    @patch("main.create_app")
    def test_ib_connect_failure_continues(
        self, mock_create_app, mock_order_router_cls, mock_ib_manager_cls,
        mock_notifier_cls, mock_config_cls,
    ):
        """IB Gateway 連線失敗時，應記錄警告但繼續啟動。"""
        from main import main

        mock_config = MagicMock()
        mock_config.ib_host = "127.0.0.1"
        mock_config.ib_port = 4002
        mock_config.ib_client_id = 1
        mock_config_cls.from_env.return_value = mock_config

        mock_ib_manager = MagicMock()
        mock_ib_manager.connect.return_value = False  # 連線失敗
        mock_ib_manager.ib = MagicMock()
        mock_ib_manager_cls.return_value = mock_ib_manager

        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        # 應正常啟動，不拋出例外
        main()

        # Flask app 仍應啟動
        mock_app.run.assert_called_once_with(host="0.0.0.0", port=5000)

    @patch("main.Config")
    @patch("main.Notifier")
    @patch("main.IBManager")
    @patch("main.OrderRouter")
    @patch("main.create_app")
    def test_logging_configured_to_stdout(
        self, mock_create_app, mock_order_router_cls, mock_ib_manager_cls,
        mock_notifier_cls, mock_config_cls,
    ):
        """驗證 logging 有設定 StreamHandler 輸出至 stdout。"""
        import sys
        from main import main

        # 清除既有 handlers，讓 basicConfig 能正常設定
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        original_level = root_logger.level
        root_logger.handlers.clear()

        try:
            mock_config = MagicMock()
            mock_config.ib_host = "127.0.0.1"
            mock_config.ib_port = 4002
            mock_config.ib_client_id = 1
            mock_config_cls.from_env.return_value = mock_config

            mock_ib_manager = MagicMock()
            mock_ib_manager.connect.return_value = True
            mock_ib_manager.ib = MagicMock()
            mock_ib_manager_cls.return_value = mock_ib_manager

            mock_app = MagicMock()
            mock_create_app.return_value = mock_app

            main()

            # 驗證 root logger 有 StreamHandler 指向 stdout
            stdout_handlers = [
                h for h in root_logger.handlers
                if isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
            ]
            assert len(stdout_handlers) >= 1
            assert root_logger.level == logging.INFO
        finally:
            # 還原 logging 狀態
            root_logger.handlers = original_handlers
            root_logger.level = original_level
