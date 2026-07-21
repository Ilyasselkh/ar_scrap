from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


BOM_UNIT_SELECTION = [
    # Comptage et conditionnement
    ("pce", "PCE"),
    ("set", "ENS"),
    ("pair", "PAIRE"),
    ("dozen", "DOUZAINE"),
    ("lot", "LOT"),
    ("box", "BOÎTE"),
    ("carton", "CARTON"),
    ("roll", "ROULEAU"),
    ("bag", "SAC"),
    ("pallet", "PALETTE"),
    # Longueur
    ("um", "µm"),
    ("mm", "mm"),
    ("cm", "cm"),
    ("dm", "dm"),
    ("m", "m"),
    ("km", "km"),
    # Surface
    ("mm2", "mm²"),
    ("cm2", "cm²"),
    ("dm2", "dm²"),
    ("m2", "m²"),
    # Volume
    ("mm3", "mm³"),
    ("cm3", "cm³"),
    ("dm3", "dm³"),
    ("m3", "m³"),
    # Masse
    ("mg", "mg"),
    ("g", "g"),
    ("kg", "kg"),
    ("t", "t"),
    # Capacité
    ("ml", "mL"),
    ("cl", "cL"),
    ("dl", "dL"),
    ("l", "L"),
    # Temps et proportion
    ("s", "s"),
    ("min", "min"),
    ("h", "h"),
    ("percent", "%"),
]


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
        BOM_UNIT_SELECTION,
        string="Unité",
        required=True,
        default="pce",
    )
    unit_label = fields.Char(string="Libellé de l'unité", compute="_compute_unit_label")

    @api.depends("unit")
    def _compute_unit_label(self):
        labels = dict(BOM_UNIT_SELECTION)
        for line in self:
            line.unit_label = labels.get(line.unit, line.unit or "")

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError(_("La quantité d'une ligne BOM doit être supérieure à zéro."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            line.product_id.message_post(
                body=_(
                    "Ligne BOM ajoutée : %(reference)s.",
                    reference=line.reference,
                )
            )
        return lines

    def write(self, vals):
        tracked_fields = {"reference", "quantity", "description", "unit"}.intersection(vals)
        result = super().write(vals)
        if tracked_fields:
            field_labels = ", ".join(
                self._fields[field_name].string for field_name in sorted(tracked_fields)
            )
            for line in self:
                line.product_id.message_post(
                    body=_(
                        "Ligne BOM %(reference)s modifiée (%(fields)s).",
                        reference=line.reference,
                        fields=field_labels,
                    )
                )
        return result

    def unlink(self):
        for line in self:
            line.product_id.message_post(
                body=_(
                    "Ligne BOM supprimée : %(reference)s.",
                    reference=line.reference,
                )
            )
        return super().unlink()
