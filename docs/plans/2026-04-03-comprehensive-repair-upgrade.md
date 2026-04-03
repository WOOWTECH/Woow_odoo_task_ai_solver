# Project AI Solver — Comprehensive Repair & Upgrade Plan

**Date:** 2026-04-03
**Version:** 18.0.1.0.0 → 18.0.1.1.0
**Approach:** Kaizen — 4 incremental batches, each independently testable

---

## Batch 1: Security & Architecture Foundation

### 1.1 Replace magic string channel identification

**File:** `models/discuss_channel.py`, `models/project_task.py`

**Problem:** `discuss_channel.py:14` uses `self.name.startswith('Task Chat:')` to identify task chat channels. Fragile — breaks if name changes, or if another module creates similarly named channels.

**Fix:** Add `is_task_chat` boolean field to `discuss.channel`. Set it to `True` during channel creation in `project_task.py`. Use this field in `message_post` override instead of name pattern matching.

```python
# discuss_channel.py
class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    is_task_chat = fields.Boolean(default=False, string='Is Task Chat Channel')

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        if self.is_task_chat:
            self._notify_task_chat_members()
        return message
```

```python
# project_task.py — in _create_chat_channel()
channel = self.env['discuss.channel'].create({
    'name': "Task Chat: %s" % self.name,
    'channel_type': 'group',
    'is_task_chat': True,  # NEW
    'channel_member_ids': [...]
})
```

**Migration:** Existing channels with `name LIKE 'Task Chat:%'` AND `channel_type='group'` need `is_task_chat=True` set via post_init_hook or data migration.

### 1.2 Replace raw SQL in file upload with ORM

**File:** `controllers/portal.py:193-205`

**Problem:** Uses `sudo().create()` then raw SQL to update `create_uid`. Bypasses ORM audit trail.

**Fix:** Create attachment with proper user context. Use `with_user()` + elevated `ir.attachment` write permissions via sudo only for the specific ACL bypass needed.

```python
# Instead of sudo().create() + raw SQL:
attachment = request.env['ir.attachment'].with_user(request.env.user).sudo().create({
    'name': ufile.filename,
    'datas': base64.b64encode(file_data),
    'res_model': 'mail.compose.message',
    'res_id': 0,
    'type': 'binary',
})
# create_uid is automatically set to the current user via with_user()
# sudo() only bypasses ACL checks, not the uid context
```

### 1.3 Fix IntegrityError handling in channel auto-membership

**File:** `controllers/portal.py:80-96`

**Problem:** After `IntegrityError`, `cr.rollback()` rolls back the entire transaction, leaving the connection in an uncertain state for subsequent operations.

**Fix:** Use a savepoint to isolate the potential failure.

```python
try:
    cr_savepoint = request.env.cr.savepoint()
    channel.write({
        'channel_member_ids': [Command.create({'partner_id': partner.id})]
    })
    cr_savepoint.close()
except IntegrityError:
    cr_savepoint.rollback()
    _logger.debug(
        "Portal user %s already member of channel %s (race condition)",
        partner.name, channel.name
    )
```

---

## Batch 2: Performance Improvements

### 2.1 Add cursor-based pagination to message history

**File:** `controllers/portal.py`, `task_chat.js`, `portal_chat.js`

**Problem:** `/chat/history` always fetches from the beginning with a fixed limit. No way to load older messages.

**Fix:** Add `before_date` parameter for cursor-based pagination. Return `has_more` flag.

```python
def chat_history(self, channel_id, limit=50, before_date=None):
    domain = [
        ('model', '=', 'discuss.channel'),
        ('res_id', '=', channel_id),
        ('message_type', 'in', ['comment', 'notification']),
    ]
    if before_date:
        domain.append(('date', '<', before_date))

    messages = request.env['mail.message'].sudo().search_read(
        domain,
        fields=['body', 'author_id', 'date', 'attachment_ids'],
        order='date desc',
        limit=limit + 1,  # fetch one extra to detect "has_more"
    )
    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]
    messages.reverse()  # return in ascending order

    # ... enrich attachments ...
    return {'messages': messages, 'has_more': has_more}
```

### 2.2 Batch bus notifications

**File:** `models/discuss_channel.py`

**Problem:** `_notify_task_chat_members()` sends individual bus notifications in a loop — N queries for N members.

**Fix:** Use `_sendmany()` for a single batch operation.

```python
def _notify_task_chat_members(self):
    notifications = [
        (member.partner_id, 'project_ai_solver/new_message', {'channel_id': self.id})
        for member in self.channel_member_ids
        if member.partner_id
    ]
    if notifications:
        self.env['bus.bus']._sendmany(notifications)
```

### 2.3 Centralize upload size limit constant

**File:** `controllers/portal.py`, `task_chat.js`, `portal_chat.js`

**Problem:** `10 * 1024 * 1024` hardcoded in 3 different files.

**Fix:** Keep `MAX_UPLOAD_SIZE` in `portal.py` (already exists). In JS files, reference a single constant. Add it to the history response as config so clients can read from server.

```python
# In chat_history response, add:
return {
    'messages': messages,
    'has_more': has_more,
    'config': {'max_upload_size': MAX_UPLOAD_SIZE},
}
```

---

## Batch 3: Frontend Quality

### 3.1 Fix OWL component lifecycle — clean up debounce timeout

**File:** `static/src/components/task_chat/task_chat.js`

**Problem:** `_busDebounce` timeout is never cleared on component destruction. Memory leak potential.

**Fix:** Add `onWillUnmount` lifecycle hook using `useEffect` or direct `owl` hook.

```javascript
import { Component, useState, useRef, onMounted, onWillUnmount, markup } from "@odoo/owl";

// In setup():
onWillUnmount(() => {
    clearTimeout(this._busDebounce);
});
```

### 3.2 Fix XSS risk in portal_chat.js message body rendering

**File:** `static/src/portal/portal_chat.js:173`

**Problem:** `${msg.body || ''}` inserts HTML directly. While Odoo's mail system sanitizes stored HTML, this is still a defense-in-depth concern.

**Fix:** Use DOMParser to safely insert HTML content rather than string concatenation.

```javascript
_renderMessages() {
    // ... inside map callback:
    const bodyDiv = document.createElement('div');
    bodyDiv.classList.add('mt-1');
    bodyDiv.innerHTML = msg.body || '';  // Odoo-sanitized HTML
    // The rest uses DOM APIs instead of string concatenation
}
```

Given the scope, a practical fix is to add a comment documenting the safety assumption and add a secondary sanitization check:

```javascript
// msg.body is HTML sanitized by Odoo's mail system (safe for innerHTML)
// As defense-in-depth, strip <script> tags if any slip through
const safeBody = (msg.body || '').replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
```

### 3.3 Add error handling and exponential backoff to portal polling

**File:** `static/src/portal/portal_chat.js`

**Problem:** Polling continues even if API returns errors repeatedly. No backoff mechanism.

**Fix:** Track consecutive errors. On repeated failures, back off exponentially. Cap at 60s.

```javascript
_startSmartPolling() {
    this._pollIntervalMs = 3000;
    this._lastMessageCount = 0;
    this._noChangeCount = 0;
    this._consecutiveErrors = 0;

    this._schedulePoll();
},

_schedulePoll() {
    this._pollTimer = setTimeout(async () => {
        await this._loadHistory();
        this._schedulePoll();
    }, this._pollIntervalMs);
},

async _loadHistory() {
    try {
        const result = await rpc('/project_ai_solver/chat/history', {
            channel_id: this.channelId,
        });
        if (result && result.messages) {
            this._consecutiveErrors = 0;  // reset on success
            this.messages = result.messages;
            this._renderMessages();
            this._adjustPollingSpeed();
        }
    } catch (e) {
        this._consecutiveErrors++;
        // Exponential backoff: 3s, 6s, 12s, 24s, 48s, 60s cap
        this._pollIntervalMs = Math.min(
            3000 * Math.pow(2, this._consecutiveErrors),
            60000
        );
        console.error('Failed to load chat history:', e);
    }
},
```

---

## Batch 4: Security Hardening & Finalization

### 4.1 Add simple rate limiting to chat endpoints

**File:** `controllers/portal.py`

**Problem:** No rate limiting — portal users can spam endpoints.

**Fix:** In-memory per-user rate limiter using a simple dict with timestamps. Limits: 60 requests/minute for history, 30 messages/minute for post, 20 uploads/minute.

```python
import time
from collections import defaultdict

_rate_limits = defaultdict(list)  # key: (user_id, endpoint) → list of timestamps
RATE_LIMITS = {
    'history': (60, 60),   # 60 requests per 60 seconds
    'post': (30, 60),      # 30 requests per 60 seconds
    'upload': (20, 60),    # 20 requests per 60 seconds
}

def _check_rate_limit(self, endpoint):
    user_id = request.env.user.id
    key = (user_id, endpoint)
    max_requests, window = RATE_LIMITS[endpoint]
    now = time.time()

    # Clean old entries
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]

    if len(_rate_limits[key]) >= max_requests:
        raise AccessError("Rate limit exceeded. Please try again later.")

    _rate_limits[key].append(now)
```

### 4.2 Handle null partner_id in channel creation

**File:** `models/project_task.py`

**Problem:** If task has no `partner_id` and no `user_ids`, channel creation silently returns empty recordset. No feedback to user.

**Fix:** Raise a `UserError` so the UI shows a clear message.

```python
from odoo.exceptions import UserError

def _create_chat_channel(self):
    self.ensure_one()
    if self.channel_id:
        return self.channel_id

    member_partners = self.env['res.partner']
    for user in self.user_ids:
        member_partners |= user.partner_id
    if self.partner_id:
        member_partners |= self.partner_id

    if not member_partners:
        raise UserError(
            "Cannot enable chat: Task '%s' has no assigned users and no customer. "
            "Please assign at least one user or set a customer first." % self.display_name
        )
    # ... rest unchanged
```

### 4.3 Update security rules — scope portal channel access to task chat only

**File:** `security/security.xml`

**Problem:** Record rule allows portal users to access ALL `group` type channels where they're a member, not just task chat channels.

**Fix:** Add `is_task_chat` field check to the domain once the field exists from Batch 1.

```xml
<field name="domain_force">[
    ('channel_member_ids.partner_id', '=', user.partner_id.id),
    ('channel_type', '=', 'group'),
    ('is_task_chat', '=', True),
]</field>
```

### 4.4 Version bump & manifest update

**File:** `__manifest__.py`

Bump version to `18.0.1.1.0` to reflect the maintenance release.

---

## Testing Strategy

After each batch:
1. Run unit tests: `odoo -u project_ai_solver --test-enable --stop-after-init`
2. Verify module update succeeds without errors
3. Manual smoke test via browser (login → Task → toggle chat → send message)

After all batches:
1. Run full E2E test suite (`test_e2e_chat.py`)
2. Verify existing channels get `is_task_chat=True` via migration
3. Verify portal user chat flow end-to-end

---

## Files Modified Summary

| File | Batch | Changes |
|------|-------|---------|
| `models/discuss_channel.py` | 1, 2 | Add `is_task_chat` field, batch bus, remove magic string |
| `models/project_task.py` | 1, 4 | Set `is_task_chat` on create, UserError on empty members |
| `controllers/portal.py` | 1, 2, 4 | ORM fix, savepoint, pagination, rate limiting, config |
| `static/src/components/task_chat/task_chat.js` | 2, 3 | Pagination support, lifecycle cleanup |
| `static/src/portal/portal_chat.js` | 2, 3 | Pagination, XSS fix, error backoff, config constant |
| `security/security.xml` | 4 | Scope rule to `is_task_chat` |
| `__manifest__.py` | 4 | Version bump |
| `tests/test_task_channel.py` | All | Update tests for new field, pagination, rate limiting |
