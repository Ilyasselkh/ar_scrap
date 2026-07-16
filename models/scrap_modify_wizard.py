from odoo import fields, models


class ArScrapModifyWizard(models.TransientModel):
    _name = "ar.scrap.modify.wizard"
    _description = "Confirmation de modification SCRAP"

    order_id = fields.Many2one(
        "ar.scrap.order",
        string="Declaration SCRAP",
        required=True,
        readonly=True,
        ondelete="cascade",
    )

    def action_confirm(self):
        self.ensure_one()
        return self.order_id.action_reset_to_cart()
