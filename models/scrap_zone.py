from odoo import fields, models


class ArScrapZone(models.Model):
    _name = "ar.scrap.zone"
    _description = "Zone de scrap"
    _order = "sequence, name, id"
    _inherit = ["mail.thread"]

    name = fields.Char(string="Zone de scrap", required=True, index=True, tracking=True)
    sequence = fields.Integer(string="Séquence", default=10, tracking=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Le nom de la zone de scrap doit être unique.",
    )
