# IB Gateway 連線管理模組
# 負責 IB Gateway 連線建立、狀態監控與自動重連

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import nest_asyncio
from ib_insync import IB

if TYPE_CHECKING:
    from app.notifier import Notifier

# 解決 Flask 同步框架與 ib_insync 非同步事件迴圈的衝突
nest_asyncio.apply()

logger = logging.getLogger(__name__)

# 預設連線參數
DEFAULT_TIMEOUT = 20  # 連線逾時秒數
MAX_RETRIES = 3       # 最大重連次數
RETRY_INTERVAL = 5    # 重連間隔秒數


class IBManager:
    """管理 ib_insync.IB 連線，提供自動重連機制。"""

    def __init__(self, host: str, port: int, client_id: int, notifier: Notifier) -> None:
        """
        初始化 IBManager。

        Args:
            host: IB Gateway 主機位址
            port: IB Gateway 連接埠
            client_id: IB API Client ID
            notifier: 通知模組，用於發送錯誤通知
        """
        self._host = host
        self._port = port
        self._client_id = client_id
        self._notifier = notifier
        self._ib = IB()

    @property
    def ib(self) -> IB:
        """取得底層 ib_insync.IB 實例。"""
        return self._ib

    @property
    def is_connected(self) -> bool:
        """檢查是否已連線至 IB Gateway。"""
        return self._ib.isConnected()

    def connect(self, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """
        嘗試連線至 IB Gateway。

        Args:
            timeout: 連線逾時秒數，預設 20 秒

        Returns:
            True 表示連線成功，False 表示連線失敗。
        """
        try:
            logger.info(
                "正在連線至 IB Gateway %s:%s (clientId=%s, timeout=%ss)",
                self._host, self._port, self._client_id, timeout,
            )
            self._ib.connect(
                host=self._host,
                port=self._port,
                clientId=self._client_id,
                timeout=timeout,
            )
            logger.info("IB Gateway 連線成功")
            return True
        except Exception:
            logger.exception("IB Gateway 連線失敗")
            return False

    def ensure_connected(self) -> bool:
        """
        確保與 IB Gateway 的連線處於活躍狀態。

        若已連線則直接回傳 True；若斷線則自動重連，
        最多重試 3 次，每次間隔 5 秒。
        全部重試失敗時透過 Notifier 發送錯誤通知。

        Returns:
            True 表示連線正常，False 表示重連全部失敗。
        """
        # 已連線，直接回傳
        if self.is_connected:
            return True

        logger.warning("IB Gateway 連線中斷，開始自動重連")

        # 嘗試重連最多 MAX_RETRIES 次
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("重連嘗試 %d/%d", attempt, MAX_RETRIES)
            if self.connect():
                logger.info("重連成功（第 %d 次嘗試）", attempt)
                return True

            # 非最後一次嘗試時等待間隔
            if attempt < MAX_RETRIES:
                logger.info("等待 %d 秒後重試", RETRY_INTERVAL)
                time.sleep(RETRY_INTERVAL)

        # 全部重試失敗，發送錯誤通知
        logger.error("IB Gateway 重連全部失敗（已嘗試 %d 次）", MAX_RETRIES)
        self._notifier.send_error_notification(
            error_type="IB Gateway 連線失敗",
            description=f"自動重連 {MAX_RETRIES} 次均失敗，請檢查 IB Gateway 狀態",
        )
        return False
