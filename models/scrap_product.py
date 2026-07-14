from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArScrapProduct(models.Model):
    _name = "ar.scrap.product"
    _description = "Référence scrap"
    _order = "sequence, name, id"

    name = fields.Char(string="Nom / Référence", required=True, index=True)
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    image_128 = fields.Image(related="image_1920", max_width=128, max_height=128, store=True)
    length = fields.Float(string="Longueur (mm)", required=True, digits=(16, 3))
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    unit_price = fields.Monetary(
        string="Prix unitaire",
        currency_field="currency_id",
        default=0.0,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Devise de la société",
        compute="_compute_company_price",
    )
    company_unit_price = fields.Monetary(
        string="Prix unitaire en devise société",
        currency_field="company_currency_id",
        compute="_compute_company_price",
    )
    company_currency_decimal_places = fields.Integer(
        string="Décimales de la devise société",
        compute="_compute_company_price",
    )
    description = fields.Text(string="Description")
    exists_in_sap = fields.Boolean(string="Référence existe dans SAP", default=False)
    zone_id = fields.Many2one(
        "ar.scrap.zone",
        string="Zone de scrap",
        ondelete="set null",
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Le nom de la référence doit être unique.",
    )

    @api.depends("unit_price", "currency_id")
    @api.depends_context("company")
    def _compute_company_price(self):
        company = self.env.company
        company_currency = company.currency_id
        conversion_date = fields.Date.context_today(self)
        for product in self:
            product.company_currency_id = company_currency
            product.company_currency_decimal_places = company_currency.decimal_places
            product.company_unit_price = product.currency_id._convert(
                product.unit_price,
                company_currency,
                company,
                conversion_date,
            ) if product.currency_id else product.unit_price

    @api.constrains("length", "unit_price")
    def _check_positive_values(self):
        for product in self:
            if product.length < 0:
                raise ValidationError(_("La longueur ne peut pas être négative."))
            if product.unit_price < 0:
                raise ValidationError(_("Le prix unitaire ne peut pas être négatif."))
