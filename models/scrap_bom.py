from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArScrapBomLine(models.Model):
    _name = "ar.scrap.bom.line"
    _description = "Ligne BOM d'une référence scrap"
    _order = "id"

    product_id = fields.Many2one(
        "ar.scrap.product",
        string="Référence scrap",
        required=True,
        ondelete="cascade",
        index=True,
    )
    reference = fields.Char(string="Référence", required=True)
    quantity = fields.Float(string="Quantité", required=True, default=1.0, digits=(16, 3))
    description = fields.Text(string="Description")
    unit = fields.Selection(
        [("pce", "PCE"), ("mm", "mm")],
        string="Unité",
        required=True,
        default="pce",
    )

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError(_("La quantité d'une ligne BOM doit être supérieure à zéro."))
