from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArScrapProductionOrder(models.Model):
    _name = "ar.scrap.production.order"
    _description = "Ordre de fabrication pour déclaration SCRAP"
    _order = "valid_from desc, name, id"
    _inherit = ["mail.thread"]

    name = fields.Char(string="Numéro OF", required=True, index=True, tracking=True)
    quantity = fields.Float(string="Quantité", required=True, digits=(16, 3), tracking=True)
    valid_from = fields.Date(string="Période de", required=True, tracking=True)
    valid_to = fields.Date(string="Période à", required=True, tracking=True)
    active = fields.Boolean(string="Actif", default=True, tracking=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Le numéro OF doit être unique.",
    )

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(order.quantity <= 0 for order in self):
            raise ValidationError(_("La quantité de l'OF doit être supérieure à zéro."))

    @api.constrains("valid_from", "valid_to")
    def _check_validity_period(self):
        for order in self:
            if order.valid_from and order.valid_to and order.valid_to < order.valid_from:
                raise ValidationError(_("La date de fin doit être supérieure ou égale à la date de début."))
