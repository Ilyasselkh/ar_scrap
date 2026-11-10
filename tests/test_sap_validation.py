from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install")
class TestSapValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.declarant = new_test_user(cls.env, login="scrap_sap_declarant")
        cls.validator_a = new_test_user(cls.env, login="scrap_sap_validator_a")
        cls.validator_b = new_test_user(cls.env, login="scrap_sap_validator_b")
        # Create the declaration before configuring SAP: existing rows must work.
        cls.order = cls.env["ar.scrap.order"].with_user(cls.declarant).create({
            "state": "sap_processing",
        })
        cls.settings = cls.env["ar.scrap.sap.settings"].search([], limit=1)
        if not cls.settings:
            cls.settings = cls.env["ar.scrap.sap.settings"].create({})
        cls.settings.validator_ids = cls.validator_a | cls.validator_b

    def _visible_in_validations(self, user):
        action = self.env.ref("ar_scrap.action_ar_scrap_order_validation")
        domain = safe_eval(action.domain, {"uid": user.id})
        return self.env["ar.scrap.order"].with_user(user).search(
            domain + [("id", "=", self.order.id)]
        )

    def test_existing_order_visible_and_approvable_by_each_assignee(self):
        for user in self.validator_a | self.validator_b:
            order = self.order.with_user(user)
            self.assertTrue(self._visible_in_validations(user))
            self.assertTrue(order.can_current_user_approve)
            order._check_current_validator()

    def test_declarant_cannot_confirm_without_assignment(self):
        self.assertTrue(self._visible_in_validations(self.declarant))
        self.assertFalse(self.order.can_current_user_approve)
        with self.assertRaises(AccessError):
            self.order._confirm_approval()

    def test_reassignment_updates_existing_order(self):
        self.assertTrue(self.order.with_user(self.validator_a).can_current_user_approve)
        self.settings.write({"validator_ids": [Command.set(self.validator_b.ids)]})
        self.assertFalse(self.order.with_user(self.validator_a).can_current_user_approve)
        self.assertTrue(self._visible_in_validations(self.validator_a))
        with self.assertRaises(AccessError):
            self.order.with_user(self.validator_a)._confirm_approval()
        self.order.with_user(self.validator_b)._check_current_validator()

    def test_no_assignment_has_no_declarant_fallback(self):
        self.settings.write({"validator_ids": [Command.clear()]})
        for user in self.declarant | self.validator_a | self.validator_b:
            with self.assertRaises(AccessError):
                self.order.with_user(user)._check_current_validator()

    def test_confirmation_archives_and_records_actual_validator(self):
        self.order.with_user(self.validator_b)._confirm_approval()
        self.assertEqual(self.order.state, "validated")
        self.assertTrue(self.order.validated_at)
        self.assertEqual(self.order.approval_history_ids.validator_id, self.validator_b)
        self.assertFalse(self._visible_in_validations(self.validator_b))
        archive = self.env.ref("ar_scrap.action_ar_scrap_order_archive")
        self.assertTrue(self.env["ar.scrap.order"].search(
            safe_eval(archive.domain) + [("id", "=", self.order.id)]
        ))

    def test_settings_are_not_editable_by_ordinary_users(self):
        with self.assertRaises(AccessError):
            self.settings.with_user(self.validator_a).write({
                "validator_ids": [Command.set(self.validator_a.ids)],
            })
