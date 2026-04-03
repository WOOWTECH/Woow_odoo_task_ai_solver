import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    is_task_chat = fields.Boolean(
        default=False,
        string='Is Task Chat Channel',
        help='Indicates this channel was created for a project task chat.',
    )

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        if self.is_task_chat:
            self._notify_task_chat_members()
        return message

    def _notify_task_chat_members(self):
        """Send bus notification to all channel members about a new chat message."""
        bus = self.env['bus.bus']
        for member in self.channel_member_ids:
            if member.partner_id:
                bus._sendone(
                    member.partner_id,
                    'project_ai_solver/new_message',
                    {'channel_id': self.id},
                )
