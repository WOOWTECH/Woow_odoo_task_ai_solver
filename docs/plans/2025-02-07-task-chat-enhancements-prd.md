# PRD: Task Chat Enhancements

## Module: project_ai_solver (Odoo 18 CE)

---

## 1. Overview

Enhance the existing Task Chat feature with two improvements:

1. **Reposition Task Chat in Portal** - Move the Task Chat widget above the "Communication history" section so it's more prominent and accessible to portal users.
2. **File/Image Attachment Support** - Allow both portal users and internal agents to upload files and images directly within the Task Chat conversation.

---

## 2. Feature 1: Reposition Task Chat in Portal

### Current State
- Task Chat card appears **below** the Communication history (chatter) section in the portal task page.
- Users must scroll past all communication history to reach the chat widget.

### Target State
- Task Chat card appears **above** the Communication history section.
- Communication history remains at the bottom of the page.
- Page structure becomes: Task Details > Task Chat > Communication History

### Technical Approach
- Change the xpath in `portal_task_chat.xml` from `position="inside"` on `#task_content` to `position="before"` on `#task_chat` (the Communication history div).

### Acceptance Criteria
- [ ] Task Chat card renders above Communication history on portal task pages
- [ ] Communication history (chatter) still renders and functions normally
- [ ] Sidebar navigation links still work correctly

---

## 3. Feature 2: File/Image Attachment Upload

### Scope
Both the **portal chat widget** and the **backend Owl chat widget** need attachment upload capability.

### User Story
As a portal user or internal agent, I want to attach files and images to my chat messages so I can share screenshots, documents, and other relevant files within the task conversation.

### Portal Chat (portal_chat.js)
- Add a file input button (paperclip icon) next to the send button
- Support multiple file selection
- Upload files via a new controller endpoint (`/project_ai_solver/chat/upload`)
- Files are attached to the `mail.message` posted to the channel
- Display attachment thumbnails/links in rendered messages
- Accepted types: images (jpg, png, gif, webp), documents (pdf, doc, docx, xls, xlsx, txt, csv, zip)
- Max file size: 10MB per file

### Backend Chat (task_chat.js)
- Add a file input button next to the send button
- Use Odoo's `/mail/attachment/upload` endpoint for file uploads
- Attach uploaded files when posting messages via `message_post`
- Display attachments in message rendering

### Controller Changes
- New endpoint: `POST /project_ai_solver/chat/upload` (type='http', auth='user')
  - Accepts: `channel_id`, `ufile` (file upload)
  - Validates channel membership
  - Creates `ir.attachment` linked to `discuss.channel`
  - Returns attachment metadata (id, name, mimetype, file_size, access_token)
- Modify `chat_post_message` to accept optional `attachment_ids` parameter
  - Attaches provided attachment IDs to the posted message

### Message Rendering
- Messages with attachments show:
  - Image attachments: inline thumbnail preview (clickable to full size)
  - Non-image attachments: file icon + filename + size (clickable to download)
- Both portal and backend renderers handle attachments

### Security
- Portal users can only upload to channels they are members of
- Attachments inherit channel access controls
- File type validation on server side
- File size limit enforced server-side (10MB)

### Acceptance Criteria
- [ ] Portal users can click a paperclip icon to select files
- [ ] Selected files upload and appear in the chat after sending
- [ ] Backend users can attach files in the Owl chat widget
- [ ] Image attachments show inline previews
- [ ] Non-image attachments show as downloadable links
- [ ] File size limit is enforced (10MB)
- [ ] Only channel members can upload files
- [ ] Both portal and backend can see each other's attachments

---

## 4. Technical Architecture

### Files Modified
| File | Change |
|------|--------|
| `templates/portal_task_chat.xml` | Change xpath to position chat before communication history |
| `static/src/portal/portal_chat.js` | Add file upload UI and upload logic |
| `controllers/portal.py` | Add upload endpoint, modify post endpoint for attachments |
| `static/src/components/task_chat/task_chat.js` | Add file upload UI and attachment handling |
| `static/src/components/task_chat/task_chat.xml` | Add file input button and attachment display |
| `static/src/components/task_chat/task_chat.scss` | Style attachment previews |

### Files Created
None - all changes are to existing files.

### API Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/project_ai_solver/chat/upload` | Upload file attachment to channel |
| POST | `/project_ai_solver/chat/post` | Post message (enhanced with attachment_ids) |
| POST | `/project_ai_solver/chat/history` | Get history (enhanced to include attachment data) |

---

## 5. Deployment

1. Edit files locally
2. `podman cp` to container volume
3. `podman exec odoo18-app odoo -d odoo18 -u project_ai_solver --stop-after-init --no-http`
4. `podman restart odoo18-app`
5. Hard refresh browser with `?debug=assets`
