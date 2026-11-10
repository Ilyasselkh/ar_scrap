from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArScrapSapSettings(models.Model):
    _name = "ar.scrap.sap.settings"
    _description = "Paramétrage du traitement SAP"

    name = fields.Char(default="Traitement SAP", required=True, readonly=True)
    singleton_key = fields.Integer(default=1, required=True)
    validator_ids = fields.Many2many(
        "res.users",
        string="Personnes autorisées à valider",
        domain="[('share', '=', False), ('active', '=', True)]",
    )

    _singleton_unique = models.Constraint(
        "UNIQUE(singleton_key)", "Un seul paramétrage SAP est autorisé."
    )
    _singleton_value = models.Constraint(
        "CHECK(singleton_key = 1)", "La clé du paramétrage SAP doit être égale à 1."
    )

    @api.constrains("validator_ids")
    def _check_validators(self):
        if any(user.share for user in self.validator_ids):
            raise ValidationError(_("Les validateurs SAP doivent être des utilisateurs internes."))

    @api.model
    def _get_validators(self):
        return self.search([], limit=1).validator_ids.filtered("active")

    def _invalidate_order_permissions(self):
        self.env["ar.scrap.order"].invalidate_model([
            "can_current_user_approve", "is_current_user_sap_validator",
        ])

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._invalidate_order_permissions()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._invalidate_order_permissions()
        return result

    def unlink(self):
        result = super().unlink()
        self._invalidate_order_permissions()
        return result
