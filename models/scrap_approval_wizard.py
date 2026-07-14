from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ArScrapApprovalWizard(models.TransientModel):
    _name = "ar.scrap.approval.wizard"
    _description = "Confirmation de décision SCRAP"

    order_id = fields.Many2one(
        "ar.scrap.order",
        string="Déclaration SCRAP",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    decision = fields.Selection(
        [("approve", "Valider"), ("refuse", "Refuser")],
        string="Décision",
        required=True,
        readonly=True,
    )
    refusal_reason = fields.Text(string="Motif de refus")

    def action_confirm(self):
        self.ensure_one()
        if self.decision == "approve":
            return self.order_id._confirm_approval()

        reason = (self.refusal_reason or "").strip()
        if not reason:
            raise ValidationError(_("Le motif de refus est obligatoire."))
        return self.order_id._confirm_refusal(reason)
