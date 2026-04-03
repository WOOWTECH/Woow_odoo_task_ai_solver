/** @odoo-module */

import { Component, useState, useRef, onMounted, onWillUnmount, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { rpc } from "@web/core/network/rpc";

const DEFAULT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024; // 10MB fallback

export class TaskChatWidget extends Component {
    static template = "project_ai_solver.TaskChat";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.notification = useService("notification");
        this._maxUploadSize = DEFAULT_MAX_UPLOAD_SIZE;

        this.state = useState({
            messages: [],
            inputValue: "",
            loading: true,
            hasMore: false,
            loadingMore: false,
            pendingAttachments: [],
            uploading: false,
        });

        this.messagesEnd = useRef("messagesEnd");
        this.messagesContainer = useRef("messagesContainer");
        this.fileInputRef = useRef("fileInput");

        // Real-time bus subscription (optional — not available in all contexts)
        try {
            this.busService = useService("bus_service");
            this.busService.subscribe("project_ai_solver/new_message", (payload) => {
                if (payload.channel_id === this.channelId) {
                    clearTimeout(this._busDebounce);
                    this._busDebounce = setTimeout(() => this.loadMessages(), 300);
                }
            });
        } catch (_e) {
            // bus_service not available (e.g. project sharing) — no real-time updates
        }

        onMounted(async () => {
            if (this.channelId) {
                await this.loadMessages();
            } else {
                this.state.loading = false;
            }
        });

        // Clean up debounce timeout on component destruction
        onWillUnmount(() => {
            clearTimeout(this._busDebounce);
        });
    }

    get channelId() {
        const value = this.props.record.data[this.props.name];
        if (!value) return 0;
        if (Array.isArray(value)) return value[0];
        if (typeof value === "number") return value;
        if (value.resId) return value.resId;
        if (value.id) return value.id;
        return 0;
    }

    async loadMessages() {
        const channelId = this.channelId;
        if (!channelId) {
            this.state.loading = false;
            return;
        }
        try {
            const result = await rpc("/project_ai_solver/chat/history", {
                channel_id: channelId,
                limit: 100,
            });
            this.state.messages = (result.messages || []).map((m) => ({
                ...m,
                body: markup(m.body || ""),
                attachments: m.attachments || [],
            }));
            this.state.hasMore = result.has_more || false;
            // Use server-provided config for upload size limit
            if (result.config && result.config.max_upload_size) {
                this._maxUploadSize = result.config.max_upload_size;
            }
        } catch (e) {
            this.notification.add("Failed to load chat messages", { type: "danger" });
        }
        this.state.loading = false;
        this.scrollToBottom();
    }

    async loadOlderMessages() {
        if (!this.state.hasMore || this.state.loadingMore) return;
        const oldest = this.state.messages[0];
        if (!oldest) return;

        this.state.loadingMore = true;
        try {
            const result = await rpc("/project_ai_solver/chat/history", {
                channel_id: this.channelId,
                limit: 50,
                before_date: oldest.date,
            });
            const olderMessages = (result.messages || []).map((m) => ({
                ...m,
                body: markup(m.body || ""),
                attachments: m.attachments || [],
            }));
            this.state.messages = [...olderMessages, ...this.state.messages];
            this.state.hasMore = result.has_more || false;
        } catch (e) {
            this.notification.add("Failed to load older messages", { type: "danger" });
        }
        this.state.loadingMore = false;
    }

    async sendMessage() {
        const body = this.state.inputValue.trim();
        const attachmentIds = this.state.pendingAttachments.map((a) => a.id);
        if (!body && !attachmentIds.length) return;

        const channelId = this.channelId;
        if (!channelId) return;

        try {
            await rpc("/project_ai_solver/chat/post", {
                channel_id: channelId,
                message_body: body || "",
                attachment_ids: attachmentIds.length ? attachmentIds : null,
            });
            this.state.inputValue = "";
            this.state.pendingAttachments = [];
            await this.loadMessages();
        } catch (e) {
            this.notification.add("Failed to send message", { type: "danger" });
        }
    }

    onClickAttach() {
        if (this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    async onFileChange(ev) {
        const files = Array.from(ev.target.files);
        if (!files.length) return;

        this.state.uploading = true;
        const channelId = this.channelId;
        const maxSize = this._maxUploadSize;
        const maxSizeMB = Math.round(maxSize / (1024 * 1024));

        for (const file of files) {
            if (file.size > maxSize) {
                this.notification.add(
                    `File "${file.name}" exceeds ${maxSizeMB}MB limit.`,
                    { type: "warning" },
                );
                continue;
            }
            try {
                const formData = new FormData();
                formData.append("channel_id", channelId);
                formData.append("ufile", file);
                formData.append("csrf_token", odoo.csrf_token || "");

                const response = await fetch("/project_ai_solver/chat/upload", {
                    method: "POST",
                    body: formData,
                });
                const result = await response.json();
                if (result && result.id) {
                    this.state.pendingAttachments = [
                        ...this.state.pendingAttachments,
                        {
                            id: result.id,
                            name: result.name || file.name,
                            mimetype: result.mimetype || file.type,
                            is_image: (result.mimetype || file.type || "").startsWith("image/"),
                        },
                    ];
                }
            } catch (e) {
                this.notification.add(`Failed to upload "${file.name}"`, { type: "danger" });
            }
        }
        this.state.uploading = false;
        // Reset input
        if (this.fileInputRef.el) {
            this.fileInputRef.el.value = "";
        }
    }

    removeAttachment(idx) {
        const newList = [...this.state.pendingAttachments];
        newList.splice(idx, 1);
        this.state.pendingAttachments = newList;
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    scrollToBottom() {
        if (this.messagesEnd.el) {
            requestAnimationFrame(() => {
                this.messagesEnd.el.scrollIntoView({ behavior: "smooth" });
            });
        }
    }

    formatFileSize(bytes) {
        if (!bytes) return "";
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    getAttachmentUrl(att, download) {
        const token = att.access_token ? `?access_token=${att.access_token}` : "";
        if (download) {
            return `/web/content/${att.id}${token ? token + "&" : "?"}download=true`;
        }
        return `/web/content/${att.id}${token}`;
    }

    getImageUrl(att) {
        const token = att.access_token ? `?access_token=${att.access_token}` : "";
        return `/web/image/${att.id}${token}`;
    }
}

registry.category("fields").add("task_chat_widget", {
    component: TaskChatWidget,
    supportedTypes: ["many2one"],
});
