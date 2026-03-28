# 實作計畫：TradingView-IBKR Bridge

## 概述

將 TradingView-IBKR Bridge 的設計拆解為漸進式的編碼任務。每個任務建立在前一個任務之上，從核心資料模型與設定開始，逐步實作各模組，最後整合所有元件。使用 Python + Flask + ib_insync，測試使用 pytest + hypothesis。

## 任務

- [x] 1. 建立專案結構與核心資料模型
  - [x] 1.1 建立專案目錄結構與依賴設定
    - 建立 `app/` 目錄，包含 `__init__.py`、`config.py`、`models.py`、`webhook.py`、`order_router.py`、`ib_manager.py`、`notifier.py`
    - 建立 `tests/` 目錄，包含 `__init__.py`、`conftest.py`
    - 建立 `requirements.txt`，包含 flask、ib_insync、nest_asyncio、requests、pytest、hypothesis
    - _需求: 10.1, 10.5_

  - [x] 1.2 實作 Config 資料類別 (`app/config.py`)
    - 實作 `Config` dataclass，包含所有環境變數欄位與預設值
    - 實作 `Config.from_env()` 類別方法，從環境變數載入設定
    - 必要變數（WEBHOOK_TOKEN、IB_HOST、IB_PORT、IB_CLIENT_ID）缺失時拋出 ValueError，錯誤訊息包含缺少的變數名稱
    - 選用變數 USE_EQUITY_PCT 預設 0.95，DISCORD_WEBHOOK_URL 預設 None
    - _需求: 9.1, 9.2, 9.4_

  - [ ]* 1.3 撰寫 Config 的屬性測試
    - **Property 11: 環境變數載入正確性**
    - **Property 12: 必要環境變數缺失檢測**
    - **驗證: 需求 9.1, 9.2, 9.4**

  - [x] 1.4 實作 SignalPayload 與 OrderResult 資料模型 (`app/models.py`)
    - 實作 `SignalPayload` dataclass 與 `from_dict()` 類別方法
    - 驗證必要欄位 (action, ticker) 存在，action 值為 "entry" 或 "close"
    - 缺少選用欄位時使用預設值
    - 實作 `OrderResult` dataclass
    - _需求: 2.1, 2.4_

  - [ ]* 1.5 撰寫 SignalPayload 的屬性測試
    - **Property 2: SignalPayload 解析往返一致性**
    - **Property 3: 無效 Payload 拒絕**
    - **驗證: 需求 2.1, 2.4, 1.5**

- [x] 2. 檢查點 - 確認核心模型測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

- [x] 3. 實作通知模組與 IB 連線管理
  - [x] 3.1 實作 Notifier 通知模組 (`app/notifier.py`)
    - 實作 `Notifier` 類別，透過 `requests.post` 發送 JSON `{"content": message}` 至 DISCORD_WEBHOOK_URL
    - 實作 `send_trade_notification()`：包含交易方向、標的、股數、價格
    - 實作 `send_error_notification()`：包含錯誤類型與描述
    - 通知發送失敗時記錄日誌，不拋出例外
    - DISCORD_WEBHOOK_URL 為 None 時靜默跳過
    - _需求: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 3.2 撰寫 Notifier 的屬性測試與單元測試
    - **Property 9: 通知訊息包含必要資訊**
    - **Property 10: 通知失敗不影響交易流程**
    - **驗證: 需求 7.1, 7.2, 7.4, 7.5**

  - [x] 3.3 實作 IBManager 連線管理 (`app/ib_manager.py`)
    - 實作 `IBManager` 類別，管理 ib_insync.IB 連線
    - 實作 `connect()` 方法，逾時 20 秒
    - 實作 `ensure_connected()` 方法，斷線時自動重連最多 3 次，每次間隔 5 秒
    - 重連全部失敗時透過 Notifier 發送錯誤通知
    - 使用 `nest_asyncio.apply()` 解決事件迴圈衝突
    - _需求: 6.1, 6.2, 6.3_

  - [ ]* 3.4 撰寫 IBManager 的屬性測試
    - **Property 8: 重連重試行為**
    - **驗證: 需求 6.2, 6.3**

- [x] 4. 實作訂單路由模組
  - [x] 4.1 實作 OrderRouter 核心邏輯 (`app/order_router.py`)
    - 實作 `OrderRouter` 類別
    - 實作 `calculate_target_shares()` 方法：`floor(NetLiquidation × USE_EQUITY_PCT ÷ 市價)`
    - 實作 `handle_entry()` 方法：查詢 NetLiquidation、持倉、市價，計算目標股數，差值 > 0 時下市價買單
    - 實作 `handle_close()` 方法：查詢持倉，持倉 > 0 時下市價賣單全部平倉
    - 目標 ≤ 持倉時跳過下單並記錄日誌；持倉為 0 時跳過平倉並記錄日誌
    - 交易成功後透過 Notifier 發送通知
    - 記錄完整計算過程日誌（NetLiquidation、持倉、市價、目標股數、下單股數）
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 8.3, 8.4_

  - [ ]* 4.2 撰寫 OrderRouter 的屬性測試
    - **Property 4: 目標股數計算公式正確性**
    - **Property 5: 進場買單數量正確性**
    - **Property 6: 出場賣單數量正確性**
    - **驗證: 需求 3.5, 3.6, 3.7, 4.2, 4.3**

- [x] 5. 檢查點 - 確認核心業務邏輯測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

- [x] 6. 實作 Webhook 端點與 Flask 應用程式整合
  - [x] 6.1 實作 Webhook 端點 (`app/webhook.py`)
    - 建立 Flask app，設定 `nest_asyncio.apply()`
    - 實作 `POST /webhook` 端點
    - 從 URL query param 讀取 token 並驗證，不符回傳 403
    - 解析 JSON body 為 SignalPayload，失敗回傳 400
    - 透過 `IBManager.ensure_connected()` 檢查連線，斷線回傳 503
    - 根據 action 呼叫 OrderRouter 對應方法
    - 記錄請求來源 IP、token 驗證結果、Signal_Payload 內容
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.5, 2.2, 2.3, 2.4, 6.4, 8.2_

  - [x] 6.2 實作應用程式入口 (`app/__init__.py` 或 `main.py`)
    - 載入 Config，缺少必要環境變數時終止啟動
    - 初始化 IBManager、Notifier、OrderRouter
    - 設定 Python logging 輸出至 stdout
    - 啟動 Flask 應用程式
    - _需求: 9.4, 8.1, 10.5_

  - [ ]* 6.3 撰寫 Webhook 端點的屬性測試與單元測試
    - **Property 1: Token 驗證正確性**
    - **Property 7: 斷線時回傳 503**
    - 單元測試：GET 請求被拒絕、無效 JSON 回傳 400
    - **驗證: 需求 1.1, 1.2, 1.3, 1.5, 6.4**

- [x] 7. 檢查點 - 確認端點整合測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

- [x] 8. 建立部署配置檔案
  - [x] 8.1 建立 Dockerfile
    - 定義 Python 執行環境
    - 安裝 requirements.txt 依賴
    - 設定應用程式啟動指令
    - _需求: 10.1_

  - [x] 8.2 建立 docker-compose.yml
    - 定義 bridge 與 ib-gateway 兩個服務
    - 設定環境變數映射
    - 設定 ib-gateway 健康檢查（nc -z localhost 4002）
    - 設定 bridge 依賴 ib-gateway 健康檢查通過後啟動
    - _需求: 10.2, 10.4, 5.1, 5.2, 5.3, 5.4_

  - [x] 8.3 建立 .env.example 與 README 部署說明
    - 列出所有環境變數與說明
    - 描述 Zeabur 平台設定步驟
    - _需求: 10.3_

- [x] 9. 最終檢查點 - 確認所有測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

## 備註

- 標記 `*` 的任務為選用，可跳過以加速 MVP 開發
- 每個任務皆標註對應的需求編號，確保可追溯性
- 檢查點確保漸進式驗證
- 屬性測試驗證通用正確性屬性，單元測試驗證特定範例與邊界條件
