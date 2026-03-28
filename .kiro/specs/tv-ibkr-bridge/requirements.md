# 需求文件

## 簡介

本系統為一個輕量級中間層橋接服務，部署於 Zeabur 雲端平台。系統接收來自 TradingView 的 Webhook JSON 交易訊號，透過 `ib_insync` 套件與容器化的 IB Gateway 溝通，實現 TQQQ 的全自動實單買賣。策略僅做多 (Long)，訊號僅包含「進場（滿倉）」與「出場（全部平倉）」兩種動作。系統同時整合 Discord Webhook 通知功能，將交易結果即時推送至使用者的 Discord 頻道。

## 詞彙表

- **Bridge_Server**：運行於 Zeabur 上的 Python Flask 應用程式，負責接收 Webhook、計算下單股數、執行交易及發送通知
- **IB_Gateway_Container**：運行於 Zeabur 上的 Docker 容器，提供無頭 (headless) 環境的 IB Gateway 服務，處理與 Interactive Brokers 交易所的加密連線
- **Webhook_Endpoint**：Bridge_Server 上的 `/webhook` POST 端點，用於接收 TradingView 發送的 JSON 交易訊號
- **Order_Router**：Bridge_Server 中負責資金控管與訂單轉換的模組，根據帳戶資產動態計算下單股數
- **Notification_Module**：Bridge_Server 中負責透過 Discord Webhook 發送文字通知的模組
- **Signal_Payload**：TradingView 發送至 Webhook_Endpoint 的 JSON 格式交易訊號，包含 action、ticker、direction 等欄位
- **NetLiquidation**：透過 ib_insync 查詢的帳戶可用總資產淨值
- **USE_EQUITY_PCT**：環境變數，定義使用帳戶資產的比例，預設值為 0.95（即 95%）
- **WEBHOOK_TOKEN**：環境變數，用於驗證 Webhook 請求合法性的密鑰字串

## 需求

### 需求 1：Webhook 端點接收與驗證

**使用者故事：** 身為交易者，我希望系統能安全地接收 TradingView 的交易訊號，以便自動執行交易策略。

#### 驗收條件

1. THE Bridge_Server SHALL 在 `/webhook` 路徑上提供一個僅接受 HTTP POST 方法的端點
2. WHEN Webhook_Endpoint 收到一個 POST 請求，THE Bridge_Server SHALL 從 URL 查詢參數中讀取 `token` 值，並與環境變數 WEBHOOK_TOKEN 進行比對驗證
3. WHEN 請求中的 token 參數與 WEBHOOK_TOKEN 不符或缺失，THE Bridge_Server SHALL 回傳 HTTP 403 狀態碼並拒絕處理該請求
4. WHEN 請求中的 token 參數驗證通過，THE Bridge_Server SHALL 解析請求 body 中的 JSON 內容為 Signal_Payload
5. IF Signal_Payload 的 JSON 格式無效或缺少必要欄位（action、ticker），THEN THE Bridge_Server SHALL 回傳 HTTP 400 狀態碼並附帶錯誤描述訊息

### 需求 2：Signal_Payload JSON 格式解析

**使用者故事：** 身為交易者，我希望系統能正確解析 TradingView 發送的 JSON 訊號，以便準確執行對應的交易動作。

#### 驗收條件

1. THE Bridge_Server SHALL 支援解析包含以下欄位的 Signal_Payload：action（字串）、ticker（字串）、direction（字串）、quantity_pct（浮點數）、price（浮點數）、timestamp（整數）、signal_score（浮點數）、strategy_id（字串）
2. WHEN Signal_Payload 的 action 欄位值為 "entry"，THE Order_Router SHALL 執行進場買入流程
3. WHEN Signal_Payload 的 action 欄位值為 "close"，THE Order_Router SHALL 執行出場平倉流程
4. IF Signal_Payload 的 action 欄位值不為 "entry" 或 "close"，THEN THE Bridge_Server SHALL 回傳 HTTP 400 狀態碼並附帶「不支援的 action 類型」錯誤訊息

### 需求 3：進場買入訂單計算與執行

**使用者故事：** 身為交易者，我希望系統在收到進場訊號時，能根據帳戶總資產動態計算應買入的 TQQQ 股數並自動下單，以便實現滿倉進場策略。

#### 驗收條件

1. WHEN Order_Router 執行進場買入流程，THE Order_Router SHALL 透過 ib_insync 查詢帳戶的 NetLiquidation 值
2. WHEN Order_Router 執行進場買入流程，THE Order_Router SHALL 透過 ib_insync 查詢目前 TQQQ 的持倉數量
3. WHEN Order_Router 執行進場買入流程，THE Order_Router SHALL 從環境變數讀取 USE_EQUITY_PCT 值，若未設定則使用預設值 0.95
4. WHEN Order_Router 執行進場買入流程，THE Order_Router SHALL 透過 ib_insync 取得 TQQQ 的最新市場價格
5. WHEN Order_Router 取得所有必要數據後，THE Order_Router SHALL 以公式 floor(NetLiquidation × USE_EQUITY_PCT ÷ 最新市價) 計算目標持有股數
6. WHEN 目標持有股數減去目前持倉數量的差值大於 0，THE Order_Router SHALL 發送一筆 TQQQ 的市價買單 (Market Order)，買入數量等於該差值
7. WHEN 目標持有股數減去目前持倉數量的差值小於或等於 0，THE Order_Router SHALL 跳過下單並記錄「無需額外買入」的日誌訊息

### 需求 4：出場平倉訂單執行

**使用者故事：** 身為交易者，我希望系統在收到出場訊號時，能自動將所有 TQQQ 持倉全部平倉，以便完整退出部位。

#### 驗收條件

1. WHEN Order_Router 執行出場平倉流程，THE Order_Router SHALL 透過 ib_insync 查詢目前 TQQQ 的持倉數量
2. WHEN TQQQ 持倉數量大於 0，THE Order_Router SHALL 發送一筆 TQQQ 的市價賣單 (Market Order)，賣出數量等於全部持倉數量
3. WHEN TQQQ 持倉數量等於 0，THE Order_Router SHALL 跳過下單並記錄「目前無持倉，無需平倉」的日誌訊息

### 需求 5：IB Gateway 容器化整合

**使用者故事：** 身為系統管理者，我希望 IB Gateway 能以容器化方式在 Zeabur 上運行，以便在無桌面環境中維持與 Interactive Brokers 的穩定連線。

#### 驗收條件

1. THE IB_Gateway_Container SHALL 使用開源的無頭 IB Gateway Docker 映像檔（如 ghcr.io/extt/ib-gateway 或 voyz/ibeam）運行
2. THE IB_Gateway_Container SHALL 透過環境變數接收 IB 帳號、密碼及交易模式（Paper 或 Live）設定
3. THE Bridge_Server SHALL 透過本地網路連接埠（4001 用於 Live 模式，4002 用於 Paper 模式）連線至 IB_Gateway_Container
4. THE Bridge_Server SHALL 提供 Docker Compose 設定檔，定義 Bridge_Server 與 IB_Gateway_Container 兩個服務的部署配置

### 需求 6：IB 連線管理與自動重連

**使用者故事：** 身為交易者，我希望系統在與 IB Gateway 斷線時能自動重新連線，以便確保交易訊號不會因連線中斷而遺失。

#### 驗收條件

1. WHEN Bridge_Server 啟動時，THE Bridge_Server SHALL 嘗試透過 ib_insync 連線至 IB_Gateway_Container，連線逾時時間為 20 秒
2. IF Bridge_Server 與 IB_Gateway_Container 的連線中斷，THEN THE Bridge_Server SHALL 自動嘗試重新連線，最多重試 3 次，每次間隔 5 秒
3. IF 重新連線 3 次均失敗，THEN THE Bridge_Server SHALL 透過 Notification_Module 發送連線失敗警告通知
4. WHILE Bridge_Server 與 IB_Gateway_Container 處於斷線狀態，THE Bridge_Server SHALL 對收到的 Webhook 請求回傳 HTTP 503 狀態碼並附帶「IB Gateway 連線中斷」錯誤訊息

### 需求 7：交易通知推送

**使用者故事：** 身為交易者，我希望在交易執行成功或發生嚴重錯誤時收到手機通知，以便即時掌握系統運作狀態。

#### 驗收條件

1. WHEN Order_Router 成功提交一筆買入或賣出訂單，THE Notification_Module SHALL 發送一則包含交易方向、標的、股數及價格的文字通知
2. WHEN Bridge_Server 發生嚴重錯誤（連線失敗、下單被拒絕），THE Notification_Module SHALL 發送一則包含錯誤類型與描述的警告通知
3. THE Notification_Module SHALL 支援透過 Discord Webhook 發送通知，使用環境變數 DISCORD_WEBHOOK_URL 進行設定，以 HTTP POST 發送 JSON `{ "content": message }` 至指定的 Discord 頻道
4. IF Notification_Module 發送通知失敗，THEN THE Bridge_Server SHALL 將通知失敗事件記錄至日誌，且該失敗不影響主要交易流程的執行

### 需求 8：日誌記錄

**使用者故事：** 身為系統管理者，我希望系統的所有關鍵操作都有完整的日誌記錄，以便在 Zeabur 日誌面板中監控與除錯。

#### 驗收條件

1. THE Bridge_Server SHALL 使用 Python logging 模組將所有日誌輸出至標準輸出 (stdout)
2. WHEN Webhook_Endpoint 收到一個請求，THE Bridge_Server SHALL 記錄該請求的來源 IP、token 驗證結果及 Signal_Payload 內容
3. WHEN Order_Router 執行計算流程，THE Bridge_Server SHALL 記錄 NetLiquidation、目前持倉量、最新市價、目標股數及需買賣股數等計算過程
4. WHEN Order_Router 提交訂單，THE Bridge_Server SHALL 記錄訂單類型、方向、股數及 IB 回傳的訂單 ID
5. WHEN Bridge_Server 發生任何錯誤，THE Bridge_Server SHALL 記錄錯誤類型、錯誤訊息及完整的堆疊追蹤 (stack trace)

### 需求 9：環境變數配置管理

**使用者故事：** 身為系統管理者，我希望所有敏感資訊與可調整參數都透過環境變數管理，以便在 Zeabur 平台上安全且靈活地配置系統。

#### 驗收條件

1. THE Bridge_Server SHALL 從環境變數載入以下必要設定：WEBHOOK_TOKEN、IB_HOST、IB_PORT、IB_CLIENT_ID
2. THE Bridge_Server SHALL 從環境變數載入以下選用設定：USE_EQUITY_PCT（預設 0.95）、DISCORD_WEBHOOK_URL
3. THE IB_Gateway_Container SHALL 從環境變數載入以下設定：IB_ACCOUNT（IB 帳號）、IB_PASSWORD（IB 密碼）、TRADING_MODE（Paper 或 Live）
4. WHEN Bridge_Server 啟動時偵測到任一必要環境變數未設定，THE Bridge_Server SHALL 立即終止啟動並輸出明確的錯誤訊息指出缺少的環境變數名稱

### 需求 10：部署配置

**使用者故事：** 身為系統管理者，我希望系統提供完整的容器化部署配置，以便快速在 Zeabur 平台上部署整套服務。

#### 驗收條件

1. THE Bridge_Server SHALL 提供一個 Dockerfile，定義 Python 執行環境、依賴套件安裝及應用程式啟動指令
2. THE Bridge_Server SHALL 提供一個 docker-compose.yml，定義 Bridge_Server 與 IB_Gateway_Container 兩個服務、網路配置及環境變數映射
3. THE Bridge_Server SHALL 提供一份部署說明文件，描述在 Zeabur 平台上設定環境變數（IB 帳號、密碼、交易模式、Webhook Token）的步驟
4. THE Bridge_Server SHALL 在 docker-compose.yml 中為 IB_Gateway_Container 設定健康檢查 (health check)，確認 IB Gateway 服務已就緒
5. THE Bridge_Server 的 Python 環境 SHALL 確保安裝並啟用 nest_asyncio 套件，以解決 Flask (同步) 與 ib_insync (非同步) 在同一事件迴圈運作時的衝突問題
