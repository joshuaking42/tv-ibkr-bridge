# Discord 通知模組
# 透過 Discord Webhook 發送交易通知與錯誤警告

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from app.config import Config

logger = logging.getLogger(__name__)


class Notifier:
    """透過 Discord Webhook 發送通知。"""

    def __init__(self, config: Config) -> None:
        self._webhook_url = config.discord_webhook_url

    def send_trade_notification(
        self, direction: str, ticker: str, shares: int, price: float
    ) -> None:
        """
        發送交易成功通知。

        訊息包含交易方向、標的、股數及價格。
        """
        message = (
            f"📈 交易通知\n"
            f"方向: {direction}\n"
            f"標的: {ticker}\n"
            f"股數: {shares}\n"
            f"價格: {price}"
        )
        self._send_discord(message)

    def send_error_notification(self, error_type: str, description: str) -> None:
        """
        發送錯誤警告通知。

        訊息包含錯誤類型與描述。
        """
        message = (
            f"🚨 錯誤通知\n"
            f"類型: {error_type}\n"
            f"描述: {description}"
        )
        self._send_discord(message)

    def _send_discord(self, message: str) -> bool:
        """
        透過 requests.post 發送 JSON {"content": message} 至 DISCORD_WEBHOOK_URL。

        - DISCORD_WEBHOOK_URL 為 None 時靜默跳過
        - 發送失敗時記錄日誌，不拋出例外

        Returns:
            True 表示發送成功，False 表示跳過或失敗。
        """
        # Webhook URL 未設定時靜默跳過
        if self._webhook_url is None:
            return False

        try:
            resp = requests.post(
                self._webhook_url,
                json={"content": message},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Discord 通知發送成功")
            return True
        except Exception:
            # 通知失敗僅記錄日誌，不拋出例外
            logger.exception("Discord 通知發送失敗")
            return False
