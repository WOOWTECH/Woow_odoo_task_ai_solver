import logging

from odoo import models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        # Only notify for task-chat group channels
        if self.channel_type == 'group' and self.name and self.name.startswith('Task Chat:'):
            self._notify_task_chat_members()
        return message

    def _notify_task_chat_members(self):
        """Send bus notification to all channel members about a new chat message."""
        for member in self.channel_member_ids:
            self.env['bus.bus']._sendone(
                member.partner_id,
                'project_ai_solver/new_message',
                {'channel_id': self.id},
            )
