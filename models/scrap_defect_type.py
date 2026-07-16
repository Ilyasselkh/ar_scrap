from odoo import fields, models, _


class ArScrapDefectType(models.Model):
    _name = "ar.scrap.defect.type"
    _description = "Type de défaut scrap"
    _order = "sequence, name, id"
    _inherit = ["mail.thread"]

    name = fields.Char(string="Type de défaut", required=True, index=True, tracking=True)
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    image_128 = fields.Image(
        related="image_1920",
        string="Miniature",
        max_width=128,
        max_height=128,
        store=True,
    )
    description = fields.Text(string="Description", tracking=True)
    sequence = fields.Integer(string="Séquence", default=10, tracking=True)
    active = fields.Boolean(string="Actif", default=True, tracking=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Le nom du type de défaut doit être unique.",
    )

    def write(self, vals):
        image_changed = "image_1920" in vals
        result = super().write(vals)
        if image_changed:
            self.message_post(body=_("Image du type de défaut modifiée."))
        return result
