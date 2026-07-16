from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArScrapProduct(models.Model):
    _name = "ar.scrap.product"
    _description = "Référence scrap"
    _order = "sequence, name, id"
    _inherit = ["mail.thread"]

    name = fields.Char(string="Nom / Référence", required=True, index=True, tracking=True)
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    image_128 = fields.Image(related="image_1920", max_width=128, max_height=128, store=True)
    length = fields.Float(string="Longueur (mm)", default=0.0, digits=(16, 3))
    bom_line_ids = fields.One2many(
        "ar.scrap.bom.line",
        "product_id",
        string="BOM",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    unit_price = fields.Monetary(
        string="Prix unitaire",
        currency_field="currency_id",
        default=0.0,
        tracking=True,
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
    description = fields.Text(string="Description", tracking=True)
    exists_in_sap = fields.Boolean(string="Référence existe dans SAP", default=False, tracking=True)
    zone_id = fields.Many2one(
        "ar.scrap.zone",
        string="Zone de scrap",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    sequence = fields.Integer(default=10, tracking=True)
    active = fields.Boolean(default=True, tracking=True)

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

    @api.constrains("unit_price")
    def _check_positive_values(self):
        for product in self:
            if product.unit_price < 0:
                raise ValidationError(_("Le prix unitaire ne peut pas être négatif."))

    def write(self, vals):
        image_changed = "image_1920" in vals
        result = super().write(vals)
        if image_changed:
            self.message_post(body=_("Image de la référence modifiée."))
        return result
