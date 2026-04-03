import base64
import logging
import time
from collections import defaultdict

from odoo import http, Command
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.addons.portal.controllers.portal import CustomerPortal
from psycopg2 import IntegrityError

_logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

# In-memory per-user rate limiter: key = (user_id, endpoint) → list of timestamps
_rate_limits = defaultdict(list)
RATE_LIMITS = {
    'history': (60, 60),   # 60 requests per 60 seconds
    'post': (30, 60),      # 30 requests per 60 seconds
    'upload': (20, 60),    # 20 requests per 60 seconds
}


class ProjectAISolverPortal(CustomerPortal):

    def _check_rate_limit(self, endpoint):
        """Simple in-memory rate limiter per user per endpoint."""
        user_id = request.env.user.id
        key = (user_id, endpoint)
        max_requests, window = RATE_LIMITS[endpoint]
        now = time.time()

        # Clean old entries outside the window
        _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]

        if len(_rate_limits[key]) >= max_requests:
            raise AccessError("Rate limit exceeded. Please try again later.")

        _rate_limits[key].append(now)

    def _task_get_page_view_values(self, task, access_token, **kwargs):
        """Extend portal task page values with chat data."""
        values = super()._task_get_page_view_values(task, access_token, **kwargs)
        values.update({
            'chat_enabled': task.chat_enabled,
            'channel_id': task.channel_id.id if task.channel_id else False,
        })
        return values

    def _validate_portal_channel_access(self, channel_id):
        """Validate that the current portal user has access to this channel.

        If the user has access to the task that owns this channel but is not
        yet a channel member, automatically add them to the channel.
        """
        partner = request.env.user.partner_id
        channel = request.env['discuss.channel'].sudo().browse(channel_id)
        if not channel.exists():
            raise AccessError("Channel not found.")

        # Check if user is already a member
        member = channel.channel_member_ids.filtered(
            lambda m: m.partner_id.id == partner.id
        )
        if member:
            return channel

        # User is not a member - check if they have access to the task
        task = request.env['project.task'].sudo().search([
            ('channel_id', '=', channel_id)
        ], limit=1)

        if not task:
            raise AccessError("You do not have access to this chat channel.")

        # Check task access: user must be collaborator, follower, or task partner
        has_access = False

        # Check if user's partner is the task's customer
        if task.partner_id and task.partner_id.id == partner.id:
            has_access = True

        # Check if user is a follower of the task
        if not has_access:
            follower = task.message_follower_ids.filtered(
                lambda f: f.partner_id.id == partner.id
            )
            if follower:
                has_access = True

        # Check project collaborators (for portal sharing)
        if not has_access and task.project_id:
            collaborator = task.project_id.collaborator_ids.filtered(
                lambda c: c.partner_id.id == partner.id
            )
            if collaborator:
                has_access = True

        if not has_access:
            raise AccessError("You do not have access to this chat channel.")

        # User has task access - add them to the channel.
        # Use savepoint to handle race condition where multiple requests
        # might try to add the same user simultaneously.
        try:
            with request.env.cr.savepoint():
                channel.write({
                    'channel_member_ids': [Command.create({'partner_id': partner.id})]
                })
            _logger.info(
                "Added portal user %s to chat channel %s for task %s",
                partner.name, channel.name, task.name
            )
        except IntegrityError:
            # User was already added by another concurrent request — savepoint
            # handles the rollback automatically, main transaction is safe.
            _logger.debug(
                "Portal user %s already a member of channel %s (race condition)",
                partner.name, channel.name
            )

        return channel

    @http.route(
        '/project_ai_solver/chat/post',
        type='json',
        auth='user',
        methods=['POST'],
    )
    def chat_post_message(self, channel_id, message_body, attachment_ids=None):
        """Post a message to a task chat channel (portal user)."""
        self._check_rate_limit('post')
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
    def chat_history(self, channel_id, limit=50, before_date=None):
        """Get message history for a task chat channel.

        Supports cursor-based pagination via `before_date` parameter.
        Returns `has_more` flag to indicate if older messages exist.
        """
        self._check_rate_limit('history')
        self._validate_portal_channel_access(channel_id)

        domain = [
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', channel_id),
            ('message_type', 'in', ['comment', 'notification']),
        ]
        if before_date:
            domain.append(('date', '<', before_date))

        # Fetch one extra to detect if more messages exist
        messages = request.env['mail.message'].sudo().search_read(
            domain,
            fields=['body', 'author_id', 'date', 'attachment_ids'],
            order='date desc',
            limit=limit + 1,
        )

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]
        # Return in ascending chronological order
        messages.reverse()

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

        return {
            'messages': messages,
            'has_more': has_more,
            'config': {
                'max_upload_size': MAX_UPLOAD_SIZE,
            },
        }

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
        self._check_rate_limit('upload')
        self._validate_portal_channel_access(channel_id)

        # Validate file size
        file_data = ufile.read()
        if len(file_data) > MAX_UPLOAD_SIZE:
            return request.make_json_response(
                {'error': 'File too large. Maximum size is %dMB.' % (MAX_UPLOAD_SIZE // (1024 * 1024))},
                status=413,
            )

        # Create attachment with the portal user's identity via with_user(),
        # and sudo() only to bypass ACL restrictions on ir.attachment.
        # This ensures create_uid is correctly set to the portal user without raw SQL.
        attachment = request.env['ir.attachment'].with_user(
            request.env.user
        ).sudo().create({
            'name': ufile.filename,
            'datas': base64.b64encode(file_data),
            'res_model': 'mail.compose.message',
            'res_id': 0,
            'type': 'binary',
        })

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
