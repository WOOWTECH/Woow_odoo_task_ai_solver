/** @odoo-module */

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.PortalTaskChat = publicWidget.Widget.extend({
    selector: '#o_portal_task_chat',

    start() {
        this.channelId = parseInt(this.el.dataset.channelId, 10);
        if (!this.channelId) return;

        this.messages = [];
        this.pendingAttachments = [];
        this._renderChatUI();
        this._loadHistory();
        this._startSmartPolling();
    },

    _renderChatUI() {
        this.el.innerHTML = `
            <div class="o_portal_chat d-flex flex-column" style="height: 400px;">
                <div class="o_portal_chat_messages flex-grow-1 overflow-auto p-3"
                     style="background: #f8f9fa;"></div>
                <div class="o_portal_chat_pending_attachments px-3 d-flex flex-wrap gap-2"></div>
                <div class="border-top p-2 d-flex gap-2 align-items-end">
                    <input type="file" class="o_portal_chat_file_input d-none"
                           multiple="multiple"
                           accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.zip"/>
                    <button class="btn btn-outline-secondary o_portal_chat_attach"
                            title="Attach file">
                        <i class="fa fa-paperclip"></i>
                    </button>
                    <textarea class="form-control o_portal_chat_input"
                              rows="2"
                              placeholder="Type a message..."></textarea>
                    <button class="btn btn-primary o_portal_chat_send">
                        <i class="fa fa-paper-plane"></i>
                    </button>
                </div>
            </div>
        `;
        this.messagesContainer = this.el.querySelector('.o_portal_chat_messages');
        this.pendingContainer = this.el.querySelector('.o_portal_chat_pending_attachments');
        this.input = this.el.querySelector('.o_portal_chat_input');
        this.sendBtn = this.el.querySelector('.o_portal_chat_send');
        this.attachBtn = this.el.querySelector('.o_portal_chat_attach');
        this.fileInput = this.el.querySelector('.o_portal_chat_file_input');

        this.sendBtn.addEventListener('click', () => this._sendMessage());
        this.input.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' && !ev.shiftKey) {
                ev.preventDefault();
                this._sendMessage();
            }
        });
        this.attachBtn.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (ev) => this._onFilesSelected(ev));
    },

    async _onFilesSelected(ev) {
        const files = Array.from(ev.target.files);
        if (!files.length) return;

        for (const file of files) {
            if (file.size > 10 * 1024 * 1024) {
                alert(`File "${file.name}" exceeds 10MB limit.`);
                continue;
            }
            try {
                const formData = new FormData();
                formData.append('channel_id', this.channelId);
                formData.append('ufile', file);
                formData.append('csrf_token', odoo.csrf_token || '');

                const response = await fetch('/project_ai_solver/chat/upload', {
                    method: 'POST',
                    body: formData,
                });
                const result = await response.json();
                if (result.error) {
                    console.error('Upload error:', result.error);
                    continue;
                }
                this.pendingAttachments.push(result);
                this._renderPendingAttachments();
            } catch (e) {
                console.error('Failed to upload file:', e);
            }
        }
        // Reset file input
        this.fileInput.value = '';
    },

    _renderPendingAttachments() {
        if (!this.pendingAttachments.length) {
            this.pendingContainer.innerHTML = '';
            return;
        }
        this.pendingContainer.innerHTML = this.pendingAttachments.map((att, idx) => `
            <div class="badge bg-light text-dark border d-flex align-items-center gap-1 py-1 px-2 mb-1">
                <i class="fa ${att.is_image ? 'fa-image' : 'fa-file-o'}"></i>
                <span class="text-truncate" style="max-width: 120px;">${this._escapeHtml(att.name)}</span>
                <button class="btn btn-sm p-0 ms-1 o_remove_attachment" data-idx="${idx}">
                    <i class="fa fa-times text-danger"></i>
                </button>
            </div>
        `).join('');

        this.pendingContainer.querySelectorAll('.o_remove_attachment').forEach((btn) => {
            btn.addEventListener('click', (ev) => {
                const idx = parseInt(ev.currentTarget.dataset.idx, 10);
                this.pendingAttachments.splice(idx, 1);
                this._renderPendingAttachments();
            });
        });
    },

    async _loadHistory() {
        try {
            const result = await rpc('/project_ai_solver/chat/history', {
                channel_id: this.channelId,
            });
            if (result && result.messages) {
                this.messages = result.messages;
                this._renderMessages();
                this._adjustPollingSpeed();
            }
        } catch (e) {
            console.error('Failed to load chat history:', e);
            this.messagesContainer.innerHTML =
                '<div class="text-center text-muted p-3">Failed to load messages.</div>';
        }
    },

    _renderMessages() {
        if (!this.messages.length) {
            this.messagesContainer.innerHTML =
                '<div class="text-center text-muted p-3">No messages yet. Start the conversation!</div>';
            return;
        }
        this.messagesContainer.innerHTML = this.messages.map((msg) => {
            let attachmentsHtml = '';
            if (msg.attachments && msg.attachments.length) {
                attachmentsHtml = '<div class="o_chat_attachments mt-2 d-flex flex-wrap gap-2">' +
                    msg.attachments.map((att) => {
                        if (att.is_image) {
                            return `<a href="/web/content/${att.id}?access_token=${att.access_token}" target="_blank" class="o_chat_attachment_img">
                                <img src="/web/image/${att.id}?access_token=${att.access_token}"
                                     alt="${this._escapeHtml(att.name)}"
                                     style="max-width: 200px; max-height: 150px; border-radius: 4px; border: 1px solid #dee2e6;"/>
                            </a>`;
                        }
                        const sizeStr = att.file_size ? ` (${this._formatFileSize(att.file_size)})` : '';
                        return `<a href="/web/content/${att.id}?download=true&access_token=${att.access_token}"
                                   target="_blank"
                                   class="badge bg-light text-dark border d-flex align-items-center gap-1 py-1 px-2 text-decoration-none">
                            <i class="fa fa-file-o"></i>
                            <span>${this._escapeHtml(att.name)}${sizeStr}</span>
                        </a>`;
                    }).join('') +
                    '</div>';
            }

            return `
                <div class="mb-2 p-2 rounded" style="background: white;">
                    <div class="d-flex justify-content-between">
                        <strong style="color: #714b67;">
                            ${this._escapeHtml(msg.author_id ? msg.author_id[1] : 'Unknown')}
                        </strong>
                        <small class="text-muted">${this._escapeHtml(msg.date || '')}</small>
                    </div>
                    <div class="mt-1">${msg.body || ''}</div>
                    ${attachmentsHtml}
                </div>
            `;
        }).join('');
        this._scrollToBottom();
    },

    async _sendMessage() {
        const body = this.input.value.trim();
        const attachmentIds = this.pendingAttachments.map((a) => a.id);

        if (!body && !attachmentIds.length) return;

        try {
            await rpc('/project_ai_solver/chat/post', {
                channel_id: this.channelId,
                message_body: body || '',
                attachment_ids: attachmentIds.length ? attachmentIds : null,
            });
            this.input.value = '';
            this.pendingAttachments = [];
            this._renderPendingAttachments();
            await this._loadHistory();
        } catch (e) {
            console.error('Failed to send message:', e);
        }
    },

    _startSmartPolling() {
        // Fast poll (3s) initially, slow down to 15s after 2 minutes of no new messages
        this._pollIntervalMs = 3000;
        this._lastMessageCount = 0;
        this._noChangeCount = 0;

        this._pollTimer = setInterval(() => {
            this._loadHistory();
        }, this._pollIntervalMs);
    },

    _adjustPollingSpeed() {
        const currentCount = this.messages.length;
        if (currentCount !== this._lastMessageCount) {
            // New messages arrived — keep fast polling, reset counter
            this._lastMessageCount = currentCount;
            this._noChangeCount = 0;
            if (this._pollIntervalMs !== 3000) {
                this._pollIntervalMs = 3000;
                clearInterval(this._pollTimer);
                this._pollTimer = setInterval(() => this._loadHistory(), 3000);
            }
        } else {
            this._noChangeCount++;
            // After 40 unchanged polls (~2 minutes at 3s), slow to 15s
            if (this._noChangeCount > 40 && this._pollIntervalMs !== 15000) {
                this._pollIntervalMs = 15000;
                clearInterval(this._pollTimer);
                this._pollTimer = setInterval(() => this._loadHistory(), 15000);
            }
        }
    },

    _scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    },

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    _formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    destroy() {
        if (this._pollTimer) {
            clearInterval(this._pollTimer);
        }
        this._super(...arguments);
    },
});
