# 環境變數配置管理模組

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """集中管理所有環境變數設定。"""

    # 必要欄位
    webhook_token: str
    ib_host: str
    ib_port: int
    ib_client_id: int

    # 選用欄位（含預設值）
    use_equity_pct: float = 0.95
    discord_webhook_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> Config:
        """從環境變數載入設定，必要變數缺失時拋出 ValueError。"""

        # 定義必要環境變數名稱
        required_vars = ["WEBHOOK_TOKEN", "IB_HOST", "IB_PORT", "IB_CLIENT_ID"]

        # 檢查缺失的必要變數
        missing = [var for var in required_vars if not os.environ.get(var)]
        if missing:
            raise ValueError(
                f"缺少必要環境變數: {', '.join(missing)}"
            )

        # 載入選用變數，未設定時使用預設值
        use_equity_pct_str = os.environ.get("USE_EQUITY_PCT")
        use_equity_pct = float(use_equity_pct_str) if use_equity_pct_str else 0.95

        discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or None

        return cls(
            webhook_token=os.environ["WEBHOOK_TOKEN"],
            ib_host=os.environ["IB_HOST"],
            ib_port=int(os.environ["IB_PORT"]),
            ib_client_id=int(os.environ["IB_CLIENT_ID"]),
            use_equity_pct=use_equity_pct,
            discord_webhook_url=discord_webhook_url,
        )
