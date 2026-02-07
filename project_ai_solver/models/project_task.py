import logging

from odoo import models, fields, api, Command

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    chat_enabled = fields.Boolean(
        string='Enable Chat',
        default=False,
    )
    channel_id = fields.Many2one(
        'discuss.channel',
        string='Chat Channel',
        ondelete='set null',
    )

    def _create_chat_channel(self):
        """Create a discuss.channel linked to this task and add members."""
        self.ensure_one()
        if self.channel_id:
            return self.channel_id

        # Collect member partners
        member_partners = self.env['res.partner']
        # Add assigned internal user(s)
        for user in self.user_ids:
            member_partners |= user.partner_id
        # Add portal customer
        if self.partner_id:
            member_partners |= self.partner_id

        if not member_partners:
            _logger.warning(
                "Task %s: cannot create chat channel — no members to add.",
                self.display_name,
            )
            return self.env['discuss.channel']

        channel = self.env['discuss.channel'].create({
            'name': "Task Chat: %s" % self.name,
            'channel_type': 'group',
            'channel_member_ids': [
                Command.create({'partner_id': partner.id})
                for partner in member_partners
            ],
        })
        self.channel_id = channel
        return channel

    def write(self, vals):
        res = super().write(vals)
        if vals.get('chat_enabled'):
            for task in self:
                if task.chat_enabled and not task.channel_id:
                    task._create_chat_channel()
        return res
