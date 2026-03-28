# 基礎映像檔：使用輕量級 Python 3.11
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 先複製依賴清單並安裝（利用 Docker 層快取）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式原始碼
COPY . .

# 開放 Flask 服務埠
EXPOSE 5000

# 啟動應用程式
CMD ["python", "main.py"]
