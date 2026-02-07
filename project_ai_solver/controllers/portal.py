import logging

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class ProjectAISolverPortal(CustomerPortal):

    def _task_get_page_view_values(self, task, access_token, **kwargs):
        """Extend portal task page values with chat data."""
        values = super()._task_get_page_view_values(task, access_token, **kwargs)
        values.update({
            'chat_enabled': task.chat_enabled,
            'channel_id': task.channel_id.id if task.channel_id else False,
        })
        return values

    def _validate_portal_channel_access(self, channel_id):
        """Validate that the current portal user has access to this channel."""
        partner = request.env.user.partner_id
        # Check if portal user is a member of this channel
        channel = request.env['discuss.channel'].sudo().browse(channel_id)
        if not channel.exists():
            raise AccessError("Channel not found.")
        member = channel.channel_member_ids.filtered(
            lambda m: m.partner_id.id == partner.id
        )
        if not member:
            raise AccessError("You do not have access to this chat channel.")
        return channel

    @http.route(
        '/project_ai_solver/chat/post',
        type='json',
        auth='user',
        methods=['POST'],
    )
    def chat_post_message(self, channel_id, message_body):
        """Post a message to a task chat channel (portal user)."""
        self._validate_portal_channel_access(channel_id)

        channel = request.env['discuss.channel'].sudo().browse(channel_id)
        channel.with_user(request.env.user).message_post(
            body=message_body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        return {'success': True}

    @http.route(
        '/project_ai_solver/chat/history',
        type='json',
        auth='user',
        methods=['POST'],
    )
    def chat_history(self, channel_id, limit=50):
        """Get message history for a task chat channel (portal user)."""
        self._validate_portal_channel_access(channel_id)

        messages = request.env['mail.message'].sudo().search_read(
            [
                ('model', '=', 'discuss.channel'),
                ('res_id', '=', channel_id),
                ('message_type', 'in', ['comment', 'notification']),
            ],
            fields=['body', 'author_id', 'date'],
            order='date asc',
            limit=limit,
        )
        return {'messages': messages}
