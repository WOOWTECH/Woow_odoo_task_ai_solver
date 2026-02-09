/** @odoo-module */

import { Component, useState, useRef, onMounted, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class TaskChatWidget extends Component {
    static template = "project_ai_solver.TaskChat";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            messages: [],
            inputValue: "",
            loading: true,
            pendingAttachments: [],
            uploading: false,
        });

        this.messagesEnd = useRef("messagesEnd");
        this.fileInputRef = useRef("fileInput");

        onMounted(async () => {
            if (this.channelId) {
                await this.loadMessages();
            } else {
                this.state.loading = false;
            }
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
            const messages = await this.orm.searchRead(
                "mail.message",
                [
                    ["model", "=", "discuss.channel"],
                    ["res_id", "=", channelId],
                    ["message_type", "in", ["comment", "notification"]],
                ],
                ["body", "author_id", "date", "attachment_ids"],
                { order: "date asc", limit: 100 }
            );

            // Fetch attachment details for messages that have them
            const allAttIds = messages.flatMap((m) => m.attachment_ids || []);
            let attMap = {};
            if (allAttIds.length) {
                try {
                    const atts = await this.orm.searchRead(
                        "ir.attachment",
                        [["id", "in", allAttIds]],
                        ["name", "mimetype", "file_size"],
                    );
                    for (const att of atts) {
                        attMap[att.id] = {
                            ...att,
                            is_image: att.mimetype && att.mimetype.startsWith("image/"),
                        };
                    }
                } catch (_e) {
                    // Portal users may lack ir.attachment read access; skip enrichment
                }
            }

            this.state.messages = messages.map((m) => ({
                ...m,
                body: markup(m.body || ""),
                attachments: (m.attachment_ids || []).map((id) => attMap[id]).filter(Boolean),
            }));
        } catch (e) {
            this.notification.add("Failed to load chat messages", { type: "danger" });
        }
        this.state.loading = false;
        this.scrollToBottom();
    }

    async sendMessage() {
        const body = this.state.inputValue.trim();
        const attachmentIds = this.state.pendingAttachments.map((a) => a.id);
        if (!body && !attachmentIds.length) return;

        const channelId = this.channelId;
        if (!channelId) return;

        try {
            const kwargs = {
                body: body || "",
                message_type: "comment",
                subtype_xmlid: "mail.mt_comment",
            };
            if (attachmentIds.length) {
                kwargs.attachment_ids = attachmentIds;
            }
            await this.orm.call("discuss.channel", "message_post", [channelId], kwargs);
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

        for (const file of files) {
            if (file.size > 10 * 1024 * 1024) {
                this.notification.add(`File "${file.name}" exceeds 10MB limit.`, { type: "warning" });
                continue;
            }
            try {
                const formData = new FormData();
                formData.append("ufile", file);
                formData.append("thread_model", "discuss.channel");
                formData.append("thread_id", channelId);
                formData.append("is_pending", "true");
                formData.append("csrf_token", odoo.csrf_token || "");

                const response = await fetch("/mail/attachment/upload", {
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
