import base64
import logging

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


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
    def chat_post_message(self, channel_id, message_body, attachment_ids=None):
        """Post a message to a task chat channel (portal user)."""
        self._validate_portal_channel_access(channel_id)

        kwargs = {
            'body': message_body,
            'message_type': 'comment',
            'subtype_xmlid': 'mail.mt_comment',
        }

        # Attach uploaded files if provided
        if attachment_ids:
            valid_attachments = request.env['ir.attachment'].sudo().browse(attachment_ids).exists()
            if valid_attachments:
                kwargs['attachment_ids'] = valid_attachments.ids

        channel = request.env['discuss.channel'].sudo().browse(channel_id)
        channel.with_user(request.env.user).message_post(**kwargs)
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
            fields=['body', 'author_id', 'date', 'attachment_ids'],
            order='date asc',
            limit=limit,
        )

        # Enrich attachment data
        for msg in messages:
            if msg.get('attachment_ids'):
                attachments = request.env['ir.attachment'].sudo().browse(msg['attachment_ids'])
                existing = attachments.exists()
                # Ensure all attachments have access tokens
                no_token = existing.filtered(lambda a: not a.access_token)
                if no_token:
                    no_token.generate_access_token()
                msg['attachments'] = [{
                    'id': att.id,
                    'name': att.name,
                    'mimetype': att.mimetype,
                    'file_size': att.file_size,
                    'access_token': att.access_token,
                    'is_image': att.mimetype and att.mimetype.startswith('image/'),
                } for att in existing]
            else:
                msg['attachments'] = []

        return {'messages': messages}

    @http.route(
        '/project_ai_solver/chat/upload',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def chat_upload_attachment(self, channel_id, ufile, **kwargs):
        """Upload a file attachment to a chat channel."""
        channel_id = int(channel_id)
        self._validate_portal_channel_access(channel_id)

        # Validate file size
        file_data = ufile.read()
        if len(file_data) > MAX_UPLOAD_SIZE:
            return request.make_json_response(
                {'error': 'File too large. Maximum size is 10MB.'},
                status=413,
            )

        # Create with res_model='mail.compose.message' so message_post links it properly.
        # _process_attachments_for_post checks: res_model == 'mail.compose.message'
        # and create_uid == current user. Using sudo() to bypass ACLs while
        # preserving the correct uid via the environment user.
        Attachment = request.env['ir.attachment'].sudo()
        attachment = Attachment.create({
            'name': ufile.filename,
            'datas': base64.b64encode(file_data),
            'res_model': 'mail.compose.message',
            'res_id': 0,
            'type': 'binary',
        })
        # Ensure create_uid matches the portal user (sudo creates as superuser)
        Attachment.env.cr.execute(
            "UPDATE ir_attachment SET create_uid = %s WHERE id = %s",
            (request.env.user.id, attachment.id)
        )
        # Ensure access token exists
        if not attachment.access_token:
            attachment.generate_access_token()

        return request.make_json_response({
            'id': attachment.id,
            'name': attachment.name,
            'mimetype': attachment.mimetype,
            'file_size': attachment.file_size,
            'access_token': attachment.access_token,
            'is_image': attachment.mimetype and attachment.mimetype.startswith('image/'),
        })
