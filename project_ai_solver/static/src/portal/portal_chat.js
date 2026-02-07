/** @odoo-module */

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.PortalTaskChat = publicWidget.Widget.extend({
    selector: '#o_portal_task_chat',

    start() {
        this.channelId = parseInt(this.el.dataset.channelId, 10);
        if (!this.channelId) return;

        this.messages = [];
        this._renderChatUI();
        this._loadHistory();
        this._startFallbackPolling();
    },

    _renderChatUI() {
        this.el.innerHTML = `
            <div class="o_portal_chat d-flex flex-column" style="height: 400px;">
                <div class="o_portal_chat_messages flex-grow-1 overflow-auto p-3"
                     style="background: #f8f9fa;"></div>
                <div class="border-top p-2 d-flex gap-2">
                    <textarea class="form-control o_portal_chat_input"
                              rows="2"
                              placeholder="Type a message..."></textarea>
                    <button class="btn btn-primary align-self-end o_portal_chat_send">
                        <i class="fa fa-paper-plane"></i>
                    </button>
                </div>
            </div>
        `;
        this.messagesContainer = this.el.querySelector('.o_portal_chat_messages');
        this.input = this.el.querySelector('.o_portal_chat_input');
        this.sendBtn = this.el.querySelector('.o_portal_chat_send');

        this.sendBtn.addEventListener('click', () => this._sendMessage());
        this.input.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' && !ev.shiftKey) {
                ev.preventDefault();
                this._sendMessage();
            }
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
        this.messagesContainer.innerHTML = this.messages.map((msg) => `
            <div class="mb-2 p-2 rounded" style="background: white;">
                <div class="d-flex justify-content-between">
                    <strong style="color: #714b67;">
                        ${this._escapeHtml(msg.author_id ? msg.author_id[1] : 'Unknown')}
                    </strong>
                    <small class="text-muted">${this._escapeHtml(msg.date || '')}</small>
                </div>
                <div class="mt-1">${msg.body || ''}</div>
            </div>
        `).join('');
        this._scrollToBottom();
    },

    async _sendMessage() {
        const body = this.input.value.trim();
        if (!body) return;

        try {
            await rpc('/project_ai_solver/chat/post', {
                channel_id: this.channelId,
                message_body: body,
            });
            this.input.value = '';
            await this._loadHistory();
        } catch (e) {
            console.error('Failed to send message:', e);
        }
    },

    _startFallbackPolling() {
        this._pollInterval = setInterval(() => {
            this._loadHistory();
        }, 5000);
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

    destroy() {
        if (this._pollInterval) {
            clearInterval(this._pollInterval);
        }
        this._super(...arguments);
    },
});
