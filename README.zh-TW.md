# Project AI Solver

> Odoo 18 任務即時聊天模組 — 讓內部客服人員與 Portal 客戶直接在專案任務上進行即時對話。

**[English README](README.md)**

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-blueviolet)](https://www.odoo.com)
[![License](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Version](https://img.shields.io/badge/Version-18.0.1.1.0-green)](https://github.com/WOOWTECH/Woow_odoo_task_ai_solver)
[![Tests](https://img.shields.io/badge/Tests-140%2B%20passing-brightgreen)]()

---

## 概覽

**Project AI Solver** 為 Odoo 18 的專案任務新增專屬即時聊天頻道，讓內部人員與 Portal 客戶可以直接在任務上下文中溝通，不再需要在電子郵件、通訊軟體和專案看板之間來回切換。

### 主要亮點

- 一鍵啟用每個任務的專屬聊天
- 後台與 Portal 雙向即時通訊
- 檔案附件上傳（最大 10 MB）搭配圖片內嵌預覽
- 游標式分頁瀏覽大量對話歷史
- 企業級安全防護：速率限制、XSS 防護

---

## 截圖展示

### 後台：任務表單 Chat 分頁

內部人員開啟專案任務，點選 **Chat** 分頁即可看到完整對話歷史。OWL 元件提供訊息輸入框、發送按鈕和檔案附件按鈕。

![後台 Chat 分頁](static/description/screenshots/01-backend-chat-tab.png)

### 後台：輸入並發送訊息

內部人員直接在 Chat 分頁輸入訊息，按 Enter 或點擊發送按鈕即可立即發送。

![後台輸入訊息](static/description/screenshots/02-backend-typing-message.png)

### 後台：訊息發送成功

發送後，訊息立即出現在對話串中。後台使用 `bus.bus` 即時推送通知。

![後台訊息已發送](static/description/screenshots/03-backend-message-sent.png)

### Portal：客戶查看任務聊天

Portal 客戶在任務詳情頁面（`/my/tasks/<id>`）看到「Task Chat」區塊。內部人員發送的訊息會顯示作者姓名和時間戳。

![Portal 任務聊天](static/description/screenshots/04-portal-task-chat.png)

### Portal：客戶回覆可見

Portal 客戶發送回覆後，訊息出現在聊天歷史中。Portal 元件使用智慧輪詢（活躍 3 秒 / 閒置 15 秒）實現近即時更新。

![Portal 回覆可見](static/description/screenshots/05-portal-reply-visible.png)

### 後台：內部人員看到 Portal 客戶的回覆

回到後台任務表單，內部人員在 Chat 分頁可以立即看到 Portal 客戶的回覆，確認完整雙向通訊運作正常。

![後台看到 Portal 回覆](static/description/screenshots/06-backend-sees-portal-reply.png)

### 任務表單：啟用聊天核取方塊

在任何專案任務上，勾選 **Enable Chat** 核取方塊即可自動建立專屬 `discuss.channel`。系統自動將指派人員和 Portal 客戶加入為成員。

![任務表單概覽](static/description/screenshots/09-task-form-overview.png)

### 對話歷史分頁

對於對話量大的任務，「Load older messages」按鈕提供游標式分頁，載入先前訊息且不會影響效能。

![對話歷史分頁](static/description/screenshots/10-chat-history-pagination.png)

---

## 系統架構

```
┌──────────────────────┐       ┌─────────────────────────┐
│   內部使用者           │       │    Portal 客戶           │
│   （後台）             │       │   （入口網站）            │
└──────────┬───────────┘       └────────────┬────────────┘
           │                                │
  ┌────────▼────────┐            ┌──────────▼──────────┐
  │ TaskChatWidget   │            │ PortalTaskChat      │
  │ (OWL 元件)       │            │ (Legacy Widget)     │
  │                  │            │                     │
  │ • bus.bus        │            │ • 智慧輪詢           │
  │   即時推送        │            │   活躍 3s / 閒置 15s │
  │ • 載入更多訊息    │            │ • 指數退避           │
  │                  │            │   錯誤時 3s→60s      │
  └────────┬─────────┘            └──────────┬──────────┘
           │                                 │
           └──────────┬──────────────────────┘
                      │
          ┌───────────▼────────────┐
          │   控制器 (portal.py)    │
          │                        │
          │  POST /chat/history    │  ← JSON-RPC，游標式分頁
          │  POST /chat/post       │  ← JSON-RPC，可帶附件
          │  POST /chat/upload     │  ← HTTP multipart，上限 10MB
          │                        │
          │  ┌──────────────────┐  │
          │  │  速率限制器       │  │  ← 每使用者、每端點
          │  │  history: 60/60s │  │
          │  │  post:    30/60s │  │
          │  │  upload:  20/60s │  │
          │  └──────────────────┘  │
          │                        │
          │  ┌──────────────────┐  │
          │  │  存取控制         │  │  ← 頻道成員驗證
          │  │  + Savepoint     │  │  ← 競態條件處理
          │  └──────────────────┘  │
          └───────────┬────────────┘
                      │
          ┌───────────▼────────────┐
          │  discuss.channel       │
          │  (is_task_chat=True)   │
          │                        │
          │  ┌──────────────────┐  │
          │  │ bus._sendone()   │  │  ← 即時通知
          │  │ 通知所有成員      │  │     每個頻道成員
          │  └──────────────────┘  │
          └───────────┬────────────┘
                      │
          ┌───────────▼────────────┐
          │  mail.message          │
          │  + ir.attachment       │
          │                        │
          │  • html_sanitize()     │  ← XSS 防護
          │  • access_token        │  ← 安全檔案下載
          │  • base64 儲存         │  ← 不接觸檔案系統
          └────────────────────────┘
```

### 資料流程

1. **啟用聊天** — 後台使用者在任務上勾選 `chat_enabled`
2. **建立頻道** — 系統建立 `discuss.channel`（`is_task_chat=True`），自動加入指派人員 + Portal 客戶
3. **發送訊息** — 使用者透過 `/chat/post` 端點發送；訊息經 `html_sanitize()` 消毒後存入 `mail.message`
4. **推送通知** — `bus._sendone()` 向所有頻道成員推送通知
5. **接收訊息** — 後台元件透過 bus 即時收到；Portal 元件透過下一次輪詢（3 秒）接收

---

## 功能特色

### 核心訊息功能
- 每個任務獨立聊天頻道，自動配置成員
- 富文字訊息內容搭配 HTML 消毒
- 檔案附件（圖片、文件）上限 10 MB
- 聊天歷史中圖片內嵌預覽
- 大量對話的游標式分頁

### 即時更新
- **後台**：`bus.bus` 推送通知（即時）
- **Portal**：智慧輪詢搭配自適應間隔（活躍 3s → 閒置 15s）
- 錯誤時指數退避（3s → 6s → 12s → ... → 最大 60s）
- 優雅的錯誤恢復與自動重試

### 安全與存取控制
- Portal 使用者僅能存取其為成員的 `is_task_chat` 頻道
- 透過任務關係（客戶、追蹤者或專案協作者）自動加入成員
- 基於 Savepoint 的競態條件處理（並發成員新增）
- 每使用者每端點的記憶體內速率限制
- HTML 消毒（伺服器端 `html_sanitize()` + 客戶端縱深防禦）
- 無原始 SQL — 所有資料庫存取透過 Odoo ORM
- 檔案附件以 base64 儲存於資料庫（無檔案系統路徑穿越風險）
- 檔案下載需要有效的 access_token

### 使用者介面
- 後台：OWL 元件嵌入任務表單 Chat 分頁
- Portal：Legacy Widget 在 `/my/tasks/<id>` 頁面
- 專案分享：相同的 OWL 元件在分享專案檢視中
- 「載入更多訊息」按鈕搭配載入動畫
- 上傳大小限制由伺服器配置驅動（非寫死）

---

## 相依模組

| 模組       | 用途                             |
|-----------|----------------------------------|
| `project` | 專案與任務模型                     |
| `mail`    | 訊息、附件、頻道                    |
| `bus`     | 即時推送通知                       |

---

## 安裝方式

1. 將此 Repo Clone 到 Odoo 18 的 addons 路徑：
   ```bash
   git clone https://github.com/WOOWTECH/Woow_odoo_task_ai_solver.git project_ai_solver
   ```

2. 更新模組列表，從「應用程式」安裝 **Project AI Solver**。

3. 或透過 CLI 安裝：
   ```bash
   odoo -d <dbname> -i project_ai_solver --stop-after-init
   ```

---

## 使用方式

1. 在後台開啟一個專案任務
2. 勾選 **Enable Chat** 核取方塊
3. 系統自動建立聊天頻道，加入指派人員與 Portal 客戶
4. 點選 **Chat** 分頁即可開始對話
5. Portal 使用者可在任務頁面（`/my/tasks/<id>`）及 Project Sharing 看到相同聊天介面

---

## 檔案結構

```
project_ai_solver/
├── __manifest__.py                    # 模組設定與 Asset Bundles（v18.0.1.1.0）
├── __init__.py
├── README.md                          # 英文文件
├── README.zh-TW.md                    # 繁體中文文件
│
├── controllers/
│   └── portal.py                      # 3 個 API 端點 + 速率限制 + 存取控制
│
├── models/
│   ├── project_task.py                # chat_enabled、channel_id、自動建立頻道
│   └── discuss_channel.py             # is_task_chat 欄位、message_post 時 bus 通知
│
├── security/
│   ├── ir.model.access.csv            # Portal ACL：讀取頻道、讀取+建立訊息
│   └── security.xml                   # Record Rules：Portal 隔離 + is_task_chat 防護
│
├── static/
│   ├── description/
│   │   └── screenshots/               # 10 張標註截圖用於文件
│   └── src/
│       ├── components/task_chat/
│       │   ├── task_chat.js            # OWL 元件（後台 + 專案分享）
│       │   ├── task_chat.xml           # OWL 範本（含分頁）
│       │   └── task_chat.scss          # 樣式
│       └── portal/
│           └── portal_chat.js          # Legacy Widget（智慧輪詢 + 指數退避）
│
├── templates/
│   └── portal_task_chat.xml            # Portal 頁面範本（繼承 portal_my_task）
│
├── views/
│   ├── project_task_views.xml          # 後台表單：Chat 分頁 + Enable Chat 核取方塊
│   └── project_sharing_views.xml       # 專案分享表單：Chat 分頁
│
├── tests/
│   └── test_task_channel.py            # 單元測試（11 個測試案例）
├── test_e2e_chat.py                    # E2E 整合測試（14 個測試）
├── test_comprehensive_v2.py            # 綜合測試套件（50+ 測試，5 輪）
├── test_commercial_v3.py               # 商業企業測試套件（80+ 測試，6 輪）
│
└── docs/plans/
    ├── 2025-02-07-task-chat-enhancements-prd.md
    ├── 2026-04-03-comprehensive-repair-upgrade.md
    └── 2026-04-03-v1.1.0-prd.md
```

---

## API 端點

| 端點 | 方法 | 驗證 | 速率限制 | 說明 |
|------|------|------|---------|------|
| `/project_ai_solver/chat/history` | POST (JSON) | User | 60 次/60s | 取得訊息歷史，支援游標式分頁 |
| `/project_ai_solver/chat/post` | POST (JSON) | User | 30 次/60s | 發送訊息，可附帶附件 ID |
| `/project_ai_solver/chat/upload` | POST (multipart) | User | 20 次/60s | 上傳檔案（上限 10 MB），回傳附件中繼資料 |

### 請求/回應範例

**POST /chat/history**
```json
// 請求
{"jsonrpc": "2.0", "method": "call", "params": {
    "channel_id": 80,
    "limit": 20,
    "before_date": "2026-04-03 10:00:00"
}}

// 回應
{"result": {
    "messages": [
        {
            "id": 123,
            "body": "<p>您好！樣品已出貨。</p>",
            "author_id": [6, "Marc Demo"],
            "date": "2026-04-03 03:33:59",
            "attachments": [
                {"id": 45, "name": "報價單.pdf", "mimetype": "application/pdf",
                 "file_size": 52480, "access_token": "abc123", "is_image": false}
            ]
        }
    ],
    "has_more": true,
    "config": {"max_upload_size": 10485760}
}}
```

**POST /chat/post**
```json
// 請求
{"jsonrpc": "2.0", "method": "call", "params": {
    "channel_id": 80,
    "message_body": "椅子已經送達！",
    "attachment_ids": [45, 46]
}}

// 回應
{"result": {"success": true}}
```

---

## 安全防護

### 威脅模型與緩解措施

| 威脅 | 緩解措施 | 測試結果 |
|------|---------|---------|
| XSS（15 種攻擊向量） | 伺服器端 `html_sanitize()` + 客戶端 script 標籤過濾 | 15/15 全部攔截 |
| SQL 注入 | Odoo ORM 參數化查詢（無原始 SQL） | 4/4 全部攔截 |
| 路徑穿越 | 附件以 base64 存於資料庫，不接觸檔案系統 | 已驗證 |
| 速率濫用 | 每使用者每端點記憶體內速率限制 | 30/60/20 限制已驗證 |
| 未授權存取 | 頻道成員驗證 + Portal Record Rules | 跨使用者拒絕已驗證 |
| 競態條件 | 基於 Savepoint 的並發成員新增 | 並發執行緒已驗證 |
| 檔案大小濫用 | 10 MB 硬限制，精確邊界執行 | 10MB+1 byte 被拒絕 |

### 安全架構

- **Record Rules**：Portal 使用者僅能讀取 `is_task_chat=True` 且自己是成員的 `discuss.channel` 記錄
- **ACL**：Portal 群組對頻道有唯讀權限，對訊息有讀取+建立權限
- **無原始 SQL**：所有先前的 `cr.execute()` 呼叫已替換為 ORM 方法
- **HTML 消毒**：Odoo 的 `html_sanitize()`（基於 lxml）中和所有危險 HTML。`<script>` 標籤被完全移除；其他危險元素做 HTML 實體編碼
- **Access Tokens**：檔案下載需要有效的 `access_token` 查詢參數

---

## 測試

### 測試套件

| 套件 | 測試數 | 覆蓋範圍 |
|------|--------|---------|
| `test_task_channel.py` | 11 | 頻道建立、成員、冪等性、存取控制 |
| `test_e2e_chat.py` | 14 | 端對端：模型欄位、檢視、訊息收發、附件 |
| `test_comprehensive_v2.py` | 50+ | 5 輪：驗證、分頁、上傳、範本、bus |
| `test_commercial_v3.py` | 80+ | 6 輪：安全、並發、資料完整性、效能、生命週期、合規 |
| Playwright 邊界測試 | 34 | 速率限制、10MB 邊界、XSS 向量、SQL 注入、Unicode |
| **合計** | **140+** | |

### 執行測試

```bash
# 單元測試（Odoo 內部執行）
odoo -d <dbname> --test-enable --test-tags project_ai_solver --stop-after-init

# 綜合測試套件（外部，需要運行中的 Odoo 實例）
python3 test_comprehensive_v2.py

# 商業企業測試套件
python3 test_commercial_v3.py
# 預期結果：106/106 通過
```

### 邊界測試結果（v18.0.1.1.0）

| 類別 | 測試數 | 通過 | 狀態 |
|------|--------|------|------|
| 速率限制邊界 | 3 | 3 | 所有限制精確執行 |
| 檔案上傳邊界 | 8 | 8 | 10MB 邊界精確、Unicode/超長檔名正常 |
| 並發測試 | 4 | 4 | 10 個並發 POST、排序完整 |
| XSS 安全（15 種向量） | 3 | 3 | 所有載荷已消毒或攔截 |
| 錯誤處理 | 16 | 16 | 空訊息/超長訊息、無效 ID、SQL 注入 |

---

## 更新日誌

### v18.0.1.1.0（2026-04-03）

- **安全**：新增每使用者每端點速率限制（60/30/20 次/60s）
- **安全**：以 ORM 取代原始 SQL 建立附件
- **安全**：新增 `is_task_chat` 欄位強化 Portal Record Rules
- **安全**：客戶端 XSS 縱深防禦（script 標籤過濾、HTML 跳脫）
- **修復**：基於 Savepoint 的競態條件處理（並發成員新增）
- **修復**：元件卸載時清理計時器洩漏（`onWillUnmount`）
- **修復**：以 `setTimeout` 鏈接取代 `setInterval` 防止輪詢堆積
- **修復**：空頻道建立時拋出 `UserError` 而非靜默警告
- **功能**：游標式分頁搭配「載入更多訊息」按鈕
- **功能**：Portal 輪詢錯誤時指數退避（3s → 60s）
- **功能**：上傳大小限制由伺服器配置驅動
- **測試**：5 個測試套件共 140+ 測試案例

### v18.0.1.0.0

- 初始版本：每任務聊天、後台 OWL 元件、Portal 元件、檔案附件

---

## 授權條款

LGPL-3
