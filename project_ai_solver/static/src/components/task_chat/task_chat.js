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
        });

        this.messagesEnd = useRef("messagesEnd");

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
                ["body", "author_id", "date"],
                { order: "date asc", limit: 100 }
            );
            this.state.messages = messages.map((m) => ({
                ...m,
                body: markup(m.body || ""),
            }));
        } catch (e) {
            this.notification.add("Failed to load chat messages", { type: "danger" });
        }
        this.state.loading = false;
        this.scrollToBottom();
    }

    async sendMessage() {
        const body = this.state.inputValue.trim();
        if (!body) return;
        const channelId = this.channelId;
        if (!channelId) return;

        try {
            await this.orm.call("discuss.channel", "message_post", [channelId], {
                body: body,
                message_type: "comment",
                subtype_xmlid: "mail.mt_comment",
            });
            this.state.inputValue = "";
            await this.loadMessages();
        } catch (e) {
            this.notification.add("Failed to send message", { type: "danger" });
        }
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
}

registry.category("fields").add("task_chat_widget", {
    component: TaskChatWidget,
    supportedTypes: ["many2one"],
});
