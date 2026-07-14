from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArScrapValidationRule(models.Model):
    _name = "ar.scrap.validation.rule"
    _description = "Règle de validation scrap"
    _order = "quantity_from, quantity_to, sequence, id"

    name = fields.Char(string="Règle", compute="_compute_name", store=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        required=True,
        readonly=True,
        default=lambda self: self.env.company.currency_id,
    )
    quantity_from = fields.Monetary(
        string="Valeur de",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )
    quantity_to = fields.Monetary(
        string="Valeur à",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )
    supervisor_ids = fields.Many2many(
        "res.users",
        "ar_scrap_rule_supervisor_rel",
        "rule_id",
        "user_id",
        string="Superviseurs",
        domain="[('share', '=', False)]",
    )
    manager_ids = fields.Many2many(
        "res.users",
        "ar_scrap_rule_manager_rel",
        "rule_id",
        "user_id",
        string="Managers",
        domain="[('share', '=', False)]",
    )
    md_ids = fields.Many2many(
        "res.users",
        "ar_scrap_rule_md_rel",
        "rule_id",
        "user_id",
        string="MD",
        domain="[('share', '=', False)]",
    )
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Active", default=True)

    @api.depends("quantity_from", "quantity_to", "currency_id")
    def _compute_name(self):
        for rule in self:
            currency = rule.currency_id
            symbol = currency.symbol or currency.name or ""
            rule.name = _(
                "De %(from_value).2f à %(to_value).2f %(currency)s",
                from_value=rule.quantity_from,
                to_value=rule.quantity_to,
                currency=symbol,
            )

    @api.constrains("quantity_from", "quantity_to")
    def _check_value_range(self):
        for rule in self:
            if rule.quantity_from < 0:
                raise ValidationError(_("La valeur minimale ne peut pas être négative."))
            if rule.quantity_to < rule.quantity_from:
                raise ValidationError(_("La valeur maximale doit être supérieure ou égale à la valeur minimale."))

    @api.constrains(
        "quantity_from",
        "quantity_to",
        "currency_id",
        "active",
        "supervisor_ids",
        "manager_ids",
        "md_ids",
    )
    def _check_active_rule(self):
        for rule in self:
            if not rule.active:
                continue
            if not (rule.supervisor_ids or rule.manager_ids or rule.md_ids):
                raise ValidationError(_("Une règle active doit contenir au moins un validateur."))
            overlap = self.search_count(
                [
                    ("id", "!=", rule.id),
                    ("active", "=", True),
                    ("currency_id", "=", rule.currency_id.id),
                    ("quantity_from", "<=", rule.quantity_to),
                    ("quantity_to", ">=", rule.quantity_from),
                ]
            )
            if overlap:
                raise ValidationError(_("Les intervalles de deux règles actives ne peuvent pas se chevaucher."))
