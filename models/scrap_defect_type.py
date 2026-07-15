from odoo import fields, models


class ArScrapDefectType(models.Model):
    _name = "ar.scrap.defect.type"
    _description = "Type de défaut scrap"
    _order = "sequence, name, id"

    name = fields.Char(string="Type de défaut", required=True, index=True)
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    image_128 = fields.Image(
        related="image_1920",
        string="Miniature",
        max_width=128,
        max_height=128,
        store=True,
    )
    description = fields.Text(string="Description")
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Actif", default=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Le nom du type de défaut doit être unique.",
    )
