# Project AI Solver

Odoo 18 即時聊天模組，讓內部客服人員與 Portal 使用者可以直接在專案任務上進行對話。

## 功能特色

- **每個任務獨立聊天頻道** - 在任務上啟用 `chat_enabled` 即自動建立專屬 `discuss.channel`，自動加入指派人員與 Portal 客戶
- **後台聊天元件** - OWL 欄位元件嵌入任務表單（Chat 分頁），支援訊息歷史、檔案附件，透過 `bus.bus` 即時更新
- **Project Sharing 支援** - 同一個聊天元件也能在 Project Sharing 檢視中正常運作
- **Portal 聊天元件** - 在 Portal 任務頁面（`/my/tasks/<id>`）使用輕量 Legacy Widget，搭配自適應智慧輪詢（活躍 3 秒 / 閒置 15 秒）
- **檔案附件** - 上傳圖片與文件（上限 10MB），圖片內嵌預覽，安全下載連結附帶 access token
- **權限控管** - Portal 使用者僅能存取所屬頻道；所有 API 端點透過 `sudo()` 驗證成員身份

## 架構

```
內部使用者（後台）               Portal 使用者
       |                              |
 TaskChatWidget (OWL)         PortalTaskChat (Legacy)
  bus.bus 訂閱即時通知           智慧輪詢 3s/15s
       |                              |
       +-------- Controller ----------+
                    |
         /chat/history  (JSON-RPC)
         /chat/post     (JSON-RPC)
         /chat/upload   (HTTP multipart)
                    |
             discuss.channel
             (group 類型, sudo)
                    |
             mail.message + ir.attachment
```

## 相依模組

| 模組       | 用途                             |
|-----------|----------------------------------|
| `project` | 專案與任務模型                     |
| `mail`    | 訊息、附件、頻道                    |
| `bus`     | 即時推送通知                       |

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

## 使用方式

1. 在後台開啟一個專案任務
2. 勾選 **Chat Enabled** 核取方塊
3. 系統自動建立聊天頻道，加入指派人員與 Portal 客戶
4. 點選 **Chat** 分頁即可開始對話
5. Portal 使用者可在任務頁面（`/my/tasks/<id>`）及 Project Sharing（`/my/projects/<id>`）看到相同的聊天介面

## 檔案結構

```
project_ai_solver/
├── __manifest__.py              # 模組設定與 Asset Bundles
├── __init__.py
├── controllers/
│   └── portal.py                # /chat/history, /chat/post, /chat/upload 端點
├── models/
│   ├── project_task.py          # chat_enabled, channel_id 欄位，自動建立頻道
│   └── discuss_channel.py       # message_post 時透過 bus.bus 發送通知
├── security/
│   ├── ir.model.access.csv      # Portal 對頻道與訊息的讀取權限
│   └── security.xml             # Portal 頻道/訊息存取的 Record Rules
├── static/src/
│   ├── components/task_chat/
│   │   ├── task_chat.js         # OWL 聊天元件（後台 + Project Sharing）
│   │   ├── task_chat.xml        # OWL 範本
│   │   └── task_chat.scss       # 樣式
│   └── portal/
│       └── portal_chat.js       # Portal Legacy Widget（智慧輪詢）
├── templates/
│   └── portal_task_chat.xml     # Portal 頁面範本（繼承 portal_my_task）
├── views/
│   ├── project_task_views.xml   # 後台表單：Chat 分頁
│   └── project_sharing_views.xml # Project Sharing 表單：Chat 分頁
├── tests/
│   └── test_task_channel.py     # 單元測試（8 個測試案例）
└── test_e2e_chat.py             # E2E 整合測試（34 個斷言）
```

## API 端點

| 端點 | 方法 | 驗證 | 說明 |
|------|------|------|------|
| `/project_ai_solver/chat/history` | POST (JSON) | User | 取得訊息歷史與附件 |
| `/project_ai_solver/chat/post` | POST (JSON) | User | 發送訊息（可附帶附件） |
| `/project_ai_solver/chat/upload` | POST (multipart) | User | 上傳檔案（上限 10MB） |

所有端點均驗證頻道成員身份，並使用 `sudo()` 存取資料。

## 測試

```bash
# 單元測試（Odoo 內部執行）
odoo -d <dbname> --test-enable --test-tags project_ai_solver --stop-after-init

# E2E 測試（需要正在運行的 Odoo 實例）
python3 test_e2e_chat.py
# 結果：34 通過、0 失敗、共 34 個
```

## 授權條款

LGPL-3
