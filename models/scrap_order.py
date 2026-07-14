from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ArScrapOrder(models.Model):
    _name = "ar.scrap.order"
    _description = "Opération de scrap"
    _order = "validated_at desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Numéro",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("Nouveau"),
    )
    user_id = fields.Many2one(
        "res.users",
        string="Validé par",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    validated_at = fields.Datetime(
        string="Date de validation",
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )
    shift = fields.Selection(
        [
            ("team_1", "Équipe 1"),
            ("team_2", "Équipe 2"),
            ("team_3", "Équipe 3"),
        ],
        string="Shift",
        readonly=True,
    )
    scrap_date = fields.Datetime(
        string="Date et heure",
        readonly=True,
    )
    notes = fields.Text(
        string="Remarques",
        readonly=True,
    )
    refusal_reason = fields.Text(
        string="Motif de refus",
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ("pending_supervisor", "En attente Superviseur"),
            ("pending_manager", "En attente Manager"),
            ("pending_md", "En attente MD"),
            ("validated", "Validée"),
            ("refused", "Refusée"),
        ],
        string="Statut",
        required=True,
        default="validated",
        readonly=True,
        index=True,
    )
    validation_rule_id = fields.Many2one(
        "ar.scrap.validation.rule",
        string="Règle appliquée",
        readonly=True,
        ondelete="restrict",
    )
    supervisor_validator_ids = fields.Many2many(
        "res.users",
        "ar_scrap_order_supervisor_rel",
        "order_id",
        "user_id",
        string="Superviseurs affectés",
        readonly=True,
    )
    manager_validator_ids = fields.Many2many(
        "res.users",
        "ar_scrap_order_manager_rel",
        "order_id",
        "user_id",
        string="Managers affectés",
        readonly=True,
    )
    md_validator_ids = fields.Many2many(
        "res.users",
        "ar_scrap_order_md_rel",
        "order_id",
        "user_id",
        string="MD affectés",
        readonly=True,
    )
    approval_history_ids = fields.One2many(
        "ar.scrap.approval.history",
        "order_id",
        string="Historique des validations",
        readonly=True,
    )
    can_current_user_approve = fields.Boolean(compute="_compute_can_current_user_approve")
    line_ids = fields.One2many(
        "ar.scrap.order.line",
        "order_id",
        string="Références scrapées",
        readonly=True,
    )
    total_quantity = fields.Float(
        string="Quantité totale",
        compute="_compute_totals",
        store=True,
        digits=(16, 3),
    )
    total_length = fields.Float(
        string="Longueur totale (mm)",
        compute="_compute_totals",
        store=True,
        digits=(16, 3),
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        required=True,
        readonly=True,
        default=lambda self: self.env.company.currency_id,
    )
    total_amount = fields.Monetary(
        string="Montant total",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )

    def init(self):
        """Convert references created with the former SCRAP/year/number format."""
        self.env.cr.execute(
            """
            UPDATE ar_scrap_order
               SET name = 'PROD-SCRAP-' ||
                   CASE
                       WHEN LENGTH((SUBSTRING(name FROM '/([0-9]+)$')::BIGINT)::TEXT) < 4
                       THEN LPAD((SUBSTRING(name FROM '/([0-9]+)$')::BIGINT)::TEXT, 4, '0')
                       ELSE (SUBSTRING(name FROM '/([0-9]+)$')::BIGINT)::TEXT
                   END
             WHERE name ~ '^SCRAP/[0-9]{4}/[0-9]+$'
            """
        )

    @api.depends("line_ids.quantity", "line_ids.total_length", "line_ids.total_amount")
    def _compute_totals(self):
        for order in self:
            order.total_quantity = sum(order.line_ids.mapped("quantity"))
            order.total_length = sum(order.line_ids.mapped("total_length"))
            order.total_amount = sum(order.line_ids.mapped("total_amount"))

    @api.depends(
        "state",
        "supervisor_validator_ids",
        "manager_validator_ids",
        "md_validator_ids",
    )
    @api.depends_context("uid")
    def _compute_can_current_user_approve(self):
        user = self.env.user
        for order in self:
            validators = order._get_current_validators()
            order.can_current_user_approve = user in validators

    def _get_current_validators(self):
        self.ensure_one()
        field_by_state = {
            "pending_supervisor": "supervisor_validator_ids",
            "pending_manager": "manager_validator_ids",
            "pending_md": "md_validator_ids",
        }
        field_name = field_by_state.get(self.state)
        return self[field_name] if field_name else self.env["res.users"]

    def get_shift_label(self):
        self.ensure_one()
        return dict(self._fields["shift"].selection).get(self.shift, "")

    def get_scrap_datetime_display(self):
        self.ensure_one()
        if not self.scrap_date:
            return ""
        localized = fields.Datetime.context_timestamp(
            self.with_context(tz=self.user_id.tz or self.env.user.tz),
            self.scrap_date,
        )
        return localized.strftime("%d/%m/%Y %H:%M")

    def get_total_amount_display(self):
        self.ensure_one()
        decimals = self.currency_id.decimal_places
        value = f"{self.total_amount:,.{decimals}f}"
        value = value.replace(",", " ").replace(".", ",")
        return f"{value} {self.currency_id.symbol or self.currency_id.name}".strip()

    def _notify_current_validators(self):
        """Queue one validation email for all users assigned to the current step."""
        self.ensure_one()
        if not self.validation_rule_id or self.state not in {
            "pending_supervisor",
            "pending_manager",
            "pending_md",
        }:
            return

        emails = list(dict.fromkeys(
            email.strip()
            for email in self._get_current_validators().mapped("partner_id.email")
            if email and email.strip()
        ))
        if not emails:
            return

        template = self.env.ref(
            "ar_scrap.mail_template_scrap_validation_required",
            raise_if_not_found=False,
        )
        if template:
            for email in emails:
                template.sudo().send_mail(
                    self.id,
                    force_send=True,
                    email_values={"email_to": email},
                )

    @api.model
    def _get_first_validation_state(self, rule):
        if rule.supervisor_ids:
            return "pending_supervisor"
        if rule.manager_ids:
            return "pending_manager"
        if rule.md_ids:
            return "pending_md"
        return "validated"

    def _get_next_validation_state(self):
        self.ensure_one()
        if self.state == "pending_supervisor" and self.manager_validator_ids:
            return "pending_manager"
        if self.state in ("pending_supervisor", "pending_manager") and self.md_validator_ids:
            return "pending_md"
        return "validated"

    def _check_current_validator(self):
        self.ensure_one()
        if self.env.user not in self._get_current_validators():
            raise AccessError(_("Vous n'êtes pas affecté à cette étape de validation."))

    def action_approve(self):
        self.ensure_one()
        self._check_current_validator()
        return self._open_decision_wizard("approve")

    def action_refuse(self):
        self.ensure_one()
        self._check_current_validator()
        return self._open_decision_wizard("refuse")

    def _open_decision_wizard(self, decision):
        self.ensure_one()
        view = self.env.ref("ar_scrap.view_ar_scrap_approval_wizard_form")
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirmer la validation") if decision == "approve" else _("Confirmer le refus"),
            "res_model": "ar.scrap.approval.wizard",
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_decision": decision,
            },
        }

    def _confirm_approval(self):
        self.ensure_one()
        self._check_current_validator()
        current_state = self.state
        self.env["ar.scrap.approval.history"].sudo().create(
            {
                "order_id": self.id,
                "level": current_state,
                "validator_id": self.env.user.id,
                "decision": "approved",
            }
        )
        next_state = self._get_next_validation_state()
        self.sudo().write({"state": next_state})
        level_label = dict(self.env["ar.scrap.approval.history"]._fields["level"].selection).get(
            current_state, current_state
        )
        self.sudo().message_post(
            body=_("Validation %(level)s effectuée par %(user)s.", level=level_label, user=self.env.user.name),
            author_id=self.env.user.partner_id.id,
        )
        self.invalidate_recordset(["state"])
        self._notify_current_validators()
        return {"type": "ir.actions.client", "tag": "reload"}

    def _confirm_refusal(self, reason):
        self.ensure_one()
        self._check_current_validator()
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(_("Le motif de refus est obligatoire."))
        current_state = self.state
        self.env["ar.scrap.approval.history"].sudo().create(
            {
                "order_id": self.id,
                "level": current_state,
                "validator_id": self.env.user.id,
                "decision": "refused",
            }
        )
        self.sudo().write({"state": "refused", "refusal_reason": reason})
        level_label = dict(self.env["ar.scrap.approval.history"]._fields["level"].selection).get(
            current_state, current_state
        )
        self.sudo().message_post(
            body=_(
                "Opération refusée au niveau %(level)s par %(user)s.<br/>Motif : %(reason)s",
                level=level_label,
                user=self.env.user.name,
                reason=reason,
            ),
            author_id=self.env.user.partner_id.id,
        )
        return {"type": "ir.actions.client", "tag": "reload"}

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            vals["user_id"] = self.env.user.id
            vals["validated_at"] = fields.Datetime.now()
            if vals.get("name", _("Nouveau")) == _("Nouveau"):
                vals["name"] = sequence.next_by_code("ar.scrap.order") or _("Nouveau")
        return super().create(vals_list)

    @api.model
    def create_from_cart(self, cart_lines, shift, scrap_datetime, notes=None):
        """Validate a cart in one transaction and return the archive record."""
        if not isinstance(cart_lines, list) or not cart_lines:
            raise ValidationError(_("Le panier est vide."))

        valid_shifts = dict(self._fields["shift"].selection)
        if shift not in valid_shifts:
            raise ValidationError(_("Sélectionnez un shift valide."))
        try:
            scrap_datetime = fields.Datetime.to_datetime(scrap_datetime)
        except (TypeError, ValueError):
            scrap_datetime = False
        if not scrap_datetime:
            raise ValidationError(_("Sélectionnez une date et une heure valides."))
        if notes is not None and not isinstance(notes, str):
            raise ValidationError(_("Le format des remarques est invalide."))
        notes = (notes or "").strip()
        if len(notes) > 1000:
            raise ValidationError(_("Les remarques ne peuvent pas dépasser 1000 caractères."))

        quantities = {}
        for item in cart_lines:
            if not isinstance(item, dict):
                raise ValidationError(_("Une ligne du panier est invalide."))
            try:
                product_id = int(item.get("product_id"))
                quantity = float(item.get("quantity"))
            except (TypeError, ValueError):
                raise ValidationError(_("La référence ou la quantité est invalide."))
            if product_id <= 0 or quantity <= 0:
                raise ValidationError(_("Les quantités scrapées doivent être supérieures à zéro."))
            quantities[product_id] = quantities.get(product_id, 0.0) + quantity

        products = self.env["ar.scrap.product"].browse(list(quantities)).exists()
        if len(products) != len(quantities) or any(not product.active for product in products):
            raise ValidationError(_("Une référence du panier n'existe plus ou a été archivée."))

        company = self.env.company
        company_currency = company.currency_id
        conversion_date = fields.Date.context_today(self)
        commands = []
        total_amount = 0.0
        for product in products:
            unit_price = product.currency_id._convert(
                product.unit_price,
                company_currency,
                company,
                conversion_date,
            )
            line_amount = company_currency.round(unit_price * quantities[product.id])
            total_amount += line_amount
            commands.append(
                fields.Command.create(
                    {
                        "product_id": product.id,
                        "product_name": product.name,
                        "product_description": product.description,
                        "product_length": product.length,
                        "unit_price": unit_price,
                        "quantity": quantities[product.id],
                    }
                )
            )
        total_amount = company_currency.round(total_amount)
        rule = self.env["ar.scrap.validation.rule"].search(
            [
                ("active", "=", True),
                ("currency_id", "=", company_currency.id),
                ("quantity_from", "<=", total_amount),
                ("quantity_to", ">=", total_amount),
            ],
            order="quantity_from, sequence, id",
            limit=1,
        )
        values = {
            "shift": shift,
            "scrap_date": scrap_datetime,
            "notes": notes,
            "currency_id": company_currency.id,
            "line_ids": commands,
            "state": "validated",
        }
        if rule:
            values.update(
                {
                    "validation_rule_id": rule.id,
                    "supervisor_validator_ids": [fields.Command.set(rule.supervisor_ids.ids)],
                    "manager_validator_ids": [fields.Command.set(rule.manager_ids.ids)],
                    "md_validator_ids": [fields.Command.set(rule.md_ids.ids)],
                    "state": self._get_first_validation_state(rule),
                }
            )
        order = self.create(values)
        order._notify_current_validators()
        return {
            "id": order.id,
            "name": order.name,
            "state": order.state,
            "state_label": dict(self._fields["state"].selection).get(order.state),
        }


class ArScrapOrderLine(models.Model):
    _name = "ar.scrap.order.line"
    _description = "Ligne d'opération de scrap"
    _order = "id"

    order_id = fields.Many2one(
        "ar.scrap.order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "ar.scrap.product",
        string="Référence",
        required=True,
        ondelete="restrict",
    )
    product_name = fields.Char(string="Nom", required=True, readonly=True)
    product_description = fields.Text(string="Description", readonly=True)
    product_length = fields.Float(string="Longueur (mm)", readonly=True, digits=(16, 3))
    quantity = fields.Float(string="Quantité scrapée", required=True, readonly=True, digits=(16, 3))
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        related="order_id.currency_id",
        store=True,
        readonly=True,
    )
    unit_price = fields.Monetary(
        string="Prix unitaire",
        currency_field="currency_id",
        required=True,
        readonly=True,
        default=0.0,
    )
    total_amount = fields.Monetary(
        string="Montant",
        currency_field="currency_id",
        compute="_compute_line_totals",
        store=True,
    )
    total_length = fields.Float(
        string="Longueur totale (mm)",
        compute="_compute_line_totals",
        store=True,
        digits=(16, 3),
    )

    @api.depends("product_length", "unit_price", "quantity")
    def _compute_line_totals(self):
        for line in self:
            line.total_length = line.product_length * line.quantity
            line.total_amount = line.unit_price * line.quantity

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError(_("La quantité scrapée doit être supérieure à zéro."))


class ArScrapApprovalHistory(models.Model):
    _name = "ar.scrap.approval.history"
    _description = "Historique de validation scrap"
    _order = "decision_date desc, id desc"

    order_id = fields.Many2one("ar.scrap.order", required=True, ondelete="cascade", index=True)
    level = fields.Selection(
        [
            ("pending_supervisor", "Superviseur"),
            ("pending_manager", "Manager"),
            ("pending_md", "MD"),
        ],
        string="Niveau",
        required=True,
        readonly=True,
    )
    validator_id = fields.Many2one("res.users", string="Validateur", required=True, readonly=True)
    decision = fields.Selection(
        [("approved", "Validée"), ("refused", "Refusée")],
        string="Décision",
        required=True,
        readonly=True,
    )
    decision_date = fields.Datetime(
        string="Date de décision",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
