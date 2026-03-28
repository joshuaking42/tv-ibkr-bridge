# Webhook 端點處理模組
# 負責接收 TradingView Webhook 請求、驗證 token、解析訊號、路由至 OrderRouter

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

import nest_asyncio
from flask import Flask, jsonify, request

from app.models import SignalPayload

if TYPE_CHECKING:
    from app.config import Config
    from app.ib_manager import IBManager
    from app.notifier import Notifier
    from app.order_router import OrderRouter

# 確保 Flask 同步環境下可正常使用 ib_insync 非同步呼叫
nest_asyncio.apply()

logger = logging.getLogger(__name__)


def create_app(
    config: Config,
    ib_manager: IBManager,
    order_router: OrderRouter,
    notifier: Notifier,
) -> Flask:
    """
    建立並回傳 Flask 應用程式實例。

    透過依賴注入方式接收所有外部元件，方便測試與彈性配置。

    Args:
        config: 應用程式設定（包含 webhook_token 等）
        ib_manager: IB Gateway 連線管理器
        order_router: 訂單路由器
        notifier: 通知模組

    Returns:
        已設定好路由的 Flask app
    """
    app = Flask(__name__)

    @app.route("/webhook", methods=["POST"])
    def webhook_handler():
        """
        接收 TradingView Webhook POST 請求。

        處理流程：
        1. 記錄請求來源 IP
        2. 從 query param 讀取 token 並驗證
        3. 解析 JSON body 為 SignalPayload
        4. 檢查 IB Gateway 連線狀態
        5. 根據 action 呼叫 OrderRouter 對應方法
        """
        # 記錄請求來源 IP
        source_ip = request.remote_addr
        logger.info("收到 Webhook 請求，來源 IP: %s", source_ip)

        # --- 步驟 1：Token 驗證 ---
        token = request.args.get("token")
        if token != config.webhook_token:
            logger.warning(
                "Token 驗證失敗 (來源 IP: %s, 提供的 token: %s)",
                source_ip,
                token if token else "缺失",
            )
            return jsonify({"error": "Forbidden", "message": "Token 驗證失敗"}), 403

        logger.info("Token 驗證通過 (來源 IP: %s)", source_ip)

        # --- 步驟 2：解析 JSON body ---
        try:
            data = request.get_json(force=True)
        except Exception:
            logger.warning("JSON 解析失敗 (來源 IP: %s)", source_ip)
            return jsonify({"error": "Bad Request", "message": "無效的 JSON 格式"}), 400

        if data is None:
            logger.warning("JSON body 為空 (來源 IP: %s)", source_ip)
            return jsonify({"error": "Bad Request", "message": "無效的 JSON 格式"}), 400

        # 解析為 SignalPayload
        try:
            signal = SignalPayload.from_dict(data)
        except ValueError as e:
            logger.warning("SignalPayload 解析失敗: %s (來源 IP: %s)", e, source_ip)
            return jsonify({"error": "Bad Request", "message": str(e)}), 400

        # 記錄 Signal_Payload 內容
        logger.info("Signal_Payload: action=%s, ticker=%s, direction=%s, price=%.2f, strategy_id=%s",
                     signal.action, signal.ticker, signal.direction, signal.price, signal.strategy_id)

        # --- 步驟 3：檢查 IB Gateway 連線 ---
        if not ib_manager.ensure_connected():
            logger.error("IB Gateway 連線中斷，無法處理請求 (來源 IP: %s)", source_ip)
            return jsonify({"error": "Service Unavailable", "message": "IB Gateway 連線中斷"}), 503

        # --- 步驟 4：根據 action 路由至對應處理方法 ---
        if signal.action == "entry":
            result = order_router.handle_entry(signal)
        else:
            # action 已在 SignalPayload.from_dict() 中驗證，此處必為 "close"
            result = order_router.handle_close(signal)

        # 回傳訂單結果
        return jsonify(asdict(result)), 200

    return app
