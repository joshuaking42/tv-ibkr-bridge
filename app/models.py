"""
資料模型定義：SignalPayload（交易訊號）與 OrderResult（訂單結果）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# 允許的 action 值
VALID_ACTIONS = ("entry", "close")


@dataclass
class SignalPayload:
    """TradingView 發送的 JSON 交易訊號結構"""

    action: str  # "entry" 進場 | "close" 平倉
    ticker: str  # 標的代碼，例如 "TQQQ"
    direction: str  # 交易方向，目前僅支援 "long"
    quantity_pct: float  # 數量百分比（保留欄位）
    price: float  # TradingView 觸發時的參考價格
    timestamp: int  # Unix 時間戳
    signal_score: float  # 訊號強度分數（保留欄位）
    strategy_id: str  # 策略識別碼

    @classmethod
    def from_dict(cls, data: dict) -> SignalPayload:
        """
        從 dict 建立 SignalPayload。

        驗證規則：
        - 必要欄位 action、ticker 必須存在
        - action 值必須為 "entry" 或 "close"
        - 選用欄位缺失時使用預設值

        Raises:
            ValueError: 缺少必要欄位或 action 值無效
        """
        # 驗證必要欄位存在
        if "action" not in data:
            raise ValueError("缺少必要欄位: action")
        if "ticker" not in data:
            raise ValueError("缺少必要欄位: ticker")

        action = data["action"]

        # 驗證 action 值為合法值
        if action not in VALID_ACTIONS:
            raise ValueError(
                f"不支援的 action 類型: {action!r}，僅支援 {VALID_ACTIONS}"
            )

        return cls(
            action=action,
            ticker=data["ticker"],
            direction=data.get("direction", "long"),
            quantity_pct=float(data.get("quantity_pct", 100.0)),
            price=float(data.get("price", 0.0)),
            timestamp=int(data.get("timestamp", 0)),
            signal_score=float(data.get("signal_score", 0.0)),
            strategy_id=data.get("strategy_id", ""),
        )


@dataclass
class OrderResult:
    """訂單執行結果"""

    success: bool  # 是否成功
    action: str  # "entry" | "close" | "skip"
    ticker: str  # 標的代碼
    shares: int  # 實際下單股數
    order_id: Optional[int]  # IB 回傳的訂單 ID
    message: str  # 描述訊息（成功/跳過/錯誤原因）
    net_liquidation: Optional[float]  # 進場時的帳戶淨值
    market_price: Optional[float]  # 下單時的市價
    target_shares: Optional[int]  # 計算出的目標股數
