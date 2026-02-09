# Project AI Solver

Real-time chat module for Odoo 18 that enables direct messaging between internal CS agents and portal users on project tasks.

## Features

- **Per-task chat channel** - Toggle `chat_enabled` on any task to auto-create a dedicated `discuss.channel` with assigned users and the portal customer
- **Backend chat widget** - OWL field widget embedded in the task form (Chat tab), with message history, file attachments, and real-time updates via `bus.bus`
- **Project Sharing support** - Same chat widget works inside the Project Sharing view for portal users
- **Portal chat widget** - Lightweight legacy widget on the portal task page (`/my/tasks/<id>`) with adaptive smart polling (3s fast / 15s idle)
- **File attachments** - Upload images and documents (up to 10MB), inline image preview, secure download links with access tokens
- **Security** - Portal users can only access channels they belong to; all API endpoints validate membership via `sudo()`

## Architecture

```
Internal User (Backend)          Portal User
        |                              |
  TaskChatWidget (OWL)         PortalTaskChat (legacy)
   bus.bus subscribe            smart polling 3s/15s
        |                              |
        +-------- Controller ----------+
                     |
          /chat/history  (JSON-RPC)
          /chat/post     (JSON-RPC)
          /chat/upload   (HTTP multipart)
                     |
              discuss.channel
              (group type, sudo)
                     |
              mail.message + ir.attachment
```

## Dependencies

| Module    | Purpose                          |
|-----------|----------------------------------|
| `project` | Project & task models             |
| `mail`    | Messaging, attachments, channels  |
| `bus`     | Real-time push notifications      |

## Installation

1. Clone this repo into your Odoo 18 addons path:
   ```bash
   git clone https://github.com/WOOWTECH/Woow_odoo_task_ai_solver.git project_ai_solver
   ```
2. Update the module list and install **Project AI Solver** from Apps.

3. Or via CLI:
   ```bash
   odoo -d <dbname> -i project_ai_solver --stop-after-init
   ```

## Usage

1. Open a project task in the backend
2. Check the **Chat Enabled** checkbox
3. A chat channel is auto-created with assigned users and the portal customer
4. Click the **Chat** tab to start messaging
5. Portal users see the same chat on their task page (`/my/tasks/<id>`) and in Project Sharing (`/my/projects/<id>`)

## File Structure

```
project_ai_solver/
├── __manifest__.py              # Module metadata & asset bundles
├── __init__.py
├── controllers/
│   └── portal.py                # /chat/history, /chat/post, /chat/upload endpoints
├── models/
│   ├── project_task.py          # chat_enabled, channel_id fields, auto-channel creation
│   └── discuss_channel.py       # bus.bus notification on message_post
├── security/
│   ├── ir.model.access.csv      # Portal read access to channels & messages
│   └── security.xml             # Record rules for portal channel/message isolation
├── static/src/
│   ├── components/task_chat/
│   │   ├── task_chat.js         # OWL chat widget (backend + project sharing)
│   │   ├── task_chat.xml        # OWL template
│   │   └── task_chat.scss       # Styles
│   └── portal/
│       └── portal_chat.js       # Legacy portal widget with smart polling
├── templates/
│   └── portal_task_chat.xml     # Portal page template (inherits portal_my_task)
├── views/
│   ├── project_task_views.xml   # Backend form: Chat tab
│   └── project_sharing_views.xml # Project Sharing form: Chat tab
├── tests/
│   └── test_task_channel.py     # Unit tests (8 cases)
└── test_e2e_chat.py             # E2E integration tests (34 assertions)
```

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/project_ai_solver/chat/history` | POST (JSON) | User | Fetch messages with attachments |
| `/project_ai_solver/chat/post` | POST (JSON) | User | Post message with optional attachments |
| `/project_ai_solver/chat/upload` | POST (multipart) | User | Upload file (max 10MB) |

All endpoints validate channel membership and use `sudo()` for data access.

## Testing

```bash
# Unit tests (inside Odoo)
odoo -d <dbname> --test-enable --test-tags project_ai_solver --stop-after-init

# E2E tests (external, requires running Odoo instance)
python3 test_e2e_chat.py
# RESULTS: 34 passed, 0 failed, 34 total
```

## License

LGPL-3
