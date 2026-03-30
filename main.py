# 應用程式入口
# 載入設定、初始化各模組、啟動 Flask 伺服器

import logging
import sys

from app.config import Config
from app.ib_manager import IBManager
from app.notifier import Notifier
from app.order_router import OrderRouter
from app.webhook import create_app


def main() -> None:
    """應用程式主函式：初始化所有元件並啟動 Flask 伺服器。"""

    # 設定 logging，輸出至 stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)

    # 載入環境變數設定，缺少必要變數時終止啟動
    try:
        config = Config.from_env()
    except ValueError as e:
        logger.error("設定載入失敗: %s", e)
        sys.exit(1)

    logger.info("設定載入完成")

    # 初始化通知模組
    notifier = Notifier(config)

    # 初始化 IB Gateway 連線管理器
    ib_manager = IBManager(
        host=config.ib_host,
        port=config.ib_port,
        client_id=config.ib_client_id,
        notifier=notifier,
    )

    # 嘗試連線至 IB Gateway（最多重試 12 次，每次間隔 10 秒）
    for attempt in range(12):
        if ib_manager.connect():
            break
        if attempt < 11:
            logger.warning("啟動時無法連線至 IB Gateway，10 秒後重試 (%d/12)", attempt + 1)
            import time
            time.sleep(10)
    else:
        logger.warning("啟動時無法連線至 IB Gateway，將在收到請求時重試")

    # 初始化訂單路由器
    order_router = OrderRouter(
        ib=ib_manager.ib,
        config=config,
        notifier=notifier,
    )

    # 建立 Flask 應用程式
    app = create_app(config, ib_manager, order_router, notifier)

    # 啟動 Flask 伺服器
    logger.info("啟動 Flask 伺服器於 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
