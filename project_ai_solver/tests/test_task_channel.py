from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestTaskChatChannel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Internal user (CS agent)
        cls.internal_user = cls.env['res.users'].create({
            'name': 'CS Agent',
            'login': 'cs_agent_test',
            'email': 'cs@test.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        # Portal user (customer)
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal Customer',
            'login': 'portal_customer_test',
            'email': 'customer@test.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

        # Another portal user (should NOT access first user's channels)
        cls.other_portal_user = cls.env['res.users'].create({
            'name': 'Other Customer',
            'login': 'other_customer_test',
            'email': 'other@test.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

        # Project
        cls.project = cls.env['project.project'].create({
            'name': 'Test Project',
        })

        # Task assigned to internal user, customer is portal user
        cls.task = cls.env['project.task'].create({
            'name': 'Test Task',
            'project_id': cls.project.id,
            'user_ids': [(6, 0, [cls.internal_user.id])],
            'partner_id': cls.portal_user.partner_id.id,
        })

        # Another task for the other portal user
        cls.other_task = cls.env['project.task'].create({
            'name': 'Other Task',
            'project_id': cls.project.id,
            'user_ids': [(6, 0, [cls.internal_user.id])],
            'partner_id': cls.other_portal_user.partner_id.id,
        })

    def test_channel_auto_creation(self):
        """Setting chat_enabled=True should auto-create a discuss.channel."""
        self.assertFalse(self.task.channel_id)
        self.task.write({'chat_enabled': True})
        self.assertTrue(self.task.channel_id)
        self.assertEqual(self.task.channel_id.channel_type, 'group')
        self.assertIn('Test Task', self.task.channel_id.name)

    def test_channel_members(self):
        """Channel should include assigned user and portal partner."""
        self.task.write({'chat_enabled': True})
        channel = self.task.channel_id
        member_partners = channel.channel_member_ids.mapped('partner_id')
        self.assertIn(self.internal_user.partner_id, member_partners)
        self.assertIn(self.portal_user.partner_id, member_partners)

    def test_channel_idempotency(self):
        """Setting chat_enabled=True twice should not create duplicate channels."""
        self.task.write({'chat_enabled': True})
        channel_1 = self.task.channel_id
        self.task.write({'chat_enabled': True})
        channel_2 = self.task.channel_id
        self.assertEqual(channel_1.id, channel_2.id)

    def test_channel_disabled(self):
        """chat_enabled=False should not create a channel."""
        self.task.write({'chat_enabled': False})
        self.assertFalse(self.task.channel_id)

    def test_portal_access_own_channel(self):
        """Portal user should be able to read their own task's channel."""
        self.task.write({'chat_enabled': True})
        channel = self.task.channel_id
        # Portal user reads their own channel
        channel_as_portal = channel.with_user(self.portal_user)
        try:
            channel_as_portal.read(['name'])
        except AccessError:
            self.fail("Portal user should be able to read own task's channel")

    def test_portal_access_denied(self):
        """Portal user should NOT be able to read another user's task channel."""
        self.other_task.write({'chat_enabled': True})
        other_channel = self.other_task.channel_id
        # First portal user tries to read the other user's channel
        with self.assertRaises(AccessError):
            other_channel.with_user(self.portal_user).read(['name'])

    def test_message_post_to_own_channel(self):
        """Portal user should be able to post to their own task's channel."""
        self.task.write({'chat_enabled': True})
        channel = self.task.channel_id
        channel.with_user(self.portal_user).message_post(
            body='Hello from portal',
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        messages = self.env['mail.message'].search([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', channel.id),
            ('body', 'like', 'Hello from portal'),
        ])
        self.assertTrue(messages)
