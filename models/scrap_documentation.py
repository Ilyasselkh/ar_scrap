from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArScrapDocumentation(models.Model):
    _name = "ar.scrap.documentation"
    _description = "Documentation scrap"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Titre", required=True)
    description = fields.Html(string="Description")
    file_data = fields.Binary(string="Fichier", attachment=True)
    file_name = fields.Char(string="Nom du fichier")
    link_url = fields.Char(string="Lien")
    created_by = fields.Many2one(
        "res.users",
        string="Créé par",
        related="create_uid",
        store=True,
        readonly=True,
    )
    created_on = fields.Datetime(
        string="Date",
        related="create_date",
        store=True,
        readonly=True,
    )

    @api.constrains("file_data", "link_url", "description")
    def _check_content(self):
        for document in self:
            if not document.file_data and not document.link_url and not document.description:
                raise ValidationError(_("Ajoutez une description, un fichier ou un lien."))
