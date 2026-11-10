from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install")
class TestDeletedOrders(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = new_test_user(cls.env, login="scrap_delete_admin", groups="base.group_system")
        cls.user = new_test_user(cls.env, login="scrap_delete_user", groups="base.group_user")
        cls.order = cls.env["ar.scrap.order"].with_user(cls.user).create({})

    def test_user_cannot_delete_or_forge_deletion(self):
        with self.assertRaises(AccessError):
            self.order.unlink()
        with self.assertRaises(AccessError):
            self.order.write({"state": "deleted"})
        with self.assertRaises(AccessError):
            self.order.create({"state": "deleted"})
        self.assertEqual(self.order.state, "draft")

    def test_admin_deletion_preserves_record_and_chatter(self):
        previous_messages = self.order.message_ids
        self.order.with_user(self.admin).unlink()
        self.assertTrue(self.order.exists())
        self.assertEqual(self.order.state, "deleted")
        self.assertEqual(self.order.deleted_by_id, self.admin)
        self.assertTrue(self.order.deleted_at)
        self.assertFalse(previous_messages - self.order.message_ids)
        notes = self.order.message_ids.filtered(
            lambda message: message.author_id == self.admin.partner_id
            and "Archive" in (message.body or "")
        )
        self.assertTrue(notes)
        self.assertIn(self.admin.name, str(notes[0].body))
        action = self.env.ref("ar_scrap.action_ar_scrap_order_deleted")
        self.assertTrue(self.env["ar.scrap.order"].with_user(self.user).search(
            safe_eval(action.domain) + [("id", "=", self.order.id)]
        ))

    def test_repeated_deletion_preserves_original_audit(self):
        self.order.with_user(self.admin).unlink()
        timestamp = self.order.deleted_at
        messages = self.order.message_ids
        self.order.with_user(self.admin).unlink()
        self.assertEqual(self.order.deleted_at, timestamp)
        self.assertEqual(self.order.message_ids, messages)

    def test_deleted_order_cannot_reenter_workflow(self):
        self.order.with_user(self.admin).unlink()
        for method in (self.order.action_modify, self.order.action_reset_to_cart):
            with self.assertRaises(ValidationError):
                method()
        with self.assertRaises(ValidationError):
            self.order.sudo().write({"state": "draft"})
        with self.assertRaises(AccessError):
            self.order.sudo().write({"deleted_by_id": self.user.id})
        with self.assertRaises(AccessError):
            self.order._check_current_validator()
