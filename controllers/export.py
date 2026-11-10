import base64
from io import BytesIO

from PIL import Image, UnidentifiedImageError, WebPImagePlugin
from odoo import http
from odoo.http import content_disposition, request
import xlsxwriter


class ScrapExport(http.Controller):
    @http.route("/ar_scrap/orders/<int:order_id>/xlsx", type="http", auth="user", methods=["GET"])
    def download(self, order_id):
        order = request.env["ar.scrap.order"].browse(order_id).exists()
        if not order:
            return request.not_found()
        order.check_access("read")
        content = self._workbook(order)
        return request.make_response(content, headers=[
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", content_disposition(f"{order.name}.xlsx")),
            ("Cache-Control", "no-store"),
        ])

    @staticmethod
    def _workbook(order):
        output = BytesIO()
        options = {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
        with xlsxwriter.Workbook(output, options) as book:
            header = book.add_format({"bold": True, "bg_color": "#265660", "font_color": "white"})
            quantity = book.add_format({"num_format": "#,##0.000", "valign": "vcenter"})
            money = book.add_format({"num_format": "#,##0." + "0" * order.currency_id.decimal_places
                                     if order.currency_id.decimal_places else "#,##0"})
            name_style = book.add_format({"valign": "vcenter"})

            def sheet(title, columns, widths):
                ws = book.add_worksheet(title)
                ws.write_row(0, 0, columns, header)
                for col, width in enumerate(widths):
                    ws.set_column(col, col, width)
                ws.freeze_panes(1, 0)
                return ws

            refs = sheet("Références scrapées", ["Nom/référence", "Description", "Quantité",
                         f"Montant total ({order.currency_id.name})", "Type de défaut", "Image du défaut",
                         "Commentaire", "Lot"], [32, 42, 15, 22, 24, 17, 42, 20])
            for row, line in enumerate(order.line_ids.with_context(bin_size=False), 1):
                refs.write_row(row, 0, [line.product_name, line.product_description or ""])
                refs.write_number(row, 2, line.quantity, quantity)
                refs.write_number(row, 3, line.total_amount, money)
                refs.write(row, 4, line.defect_type_name or "")
                refs.write_row(row, 6, [line.defect_comment or "", line.lot or ""])
                if line.defect_type_image:
                    source = BytesIO(base64.b64decode(line.defect_type_image))
                    try:
                        img = Image.open(source)
                    except UnidentifiedImageError:
                        source.seek(0)
                        if source.getvalue()[8:12] != b"WEBP":
                            refs.write(row, 5, "Image indisponible")
                            continue
                        img = WebPImagePlugin.WebPImageFile(source)
                    with img:
                        img.thumbnail((64, 64))
                        image = BytesIO()
                        img.convert("RGBA").save(image, format="PNG")
                    refs.set_row(row, 52)
                    refs.insert_image(row, 5, "defaut.png", {"image_data": image, "object_position": 1})

            detail = sheet("Détail des calculs BOM", ["Nom/référence", "Référence composant",
                           "Composant (description)", "Quantité BOM", "Quantité scrapée", "Calcul", "Résultat"],
                           [32, 24, 42, 18, 18, 18, 18])
            groups, totals = order._bom_breakdown()
            row = 1
            for name, components in groups.items():
                if not components:
                    continue
                first = row
                for code, desc, bom_qty, scrap_qty, value in components:
                    detail.write_row(row, 1, [code, desc or "Sans description"])
                    detail.write_row(row, 3, [bom_qty, scrap_qty], quantity)
                    detail.write_formula(row, 5, f"=D{row+1}*E{row+1}", quantity, value)
                    detail.write_formula(row, 6, f"=F{row+1}", quantity, value)
                    row += 1
                if row - first > 1:
                    detail.merge_range(first, 0, row - 1, 0, name, name_style)
                else:
                    detail.write(first, 0, name, name_style)

            summary = sheet("Totaux par composant", ["Référence composant", "Composant (description)", "Total"],
                            [26, 42, 18])
            for row, (description, total) in enumerate(totals.items(), 1):
                summary.write_row(row, 0, [", ".join(total["codes"]), description or "Sans description"])
                summary.write_number(row, 2, total["quantity"], quantity)
            sap_row = len(totals) + 3
            sap_label = book.add_format({
                "bold": True, "bg_color": "#E7F3F1", "text_wrap": True, "valign": "vcenter",
            })
            sap_value = book.add_format({
                "bold": True, "bg_color": "#E7F3F1", "num_format": "#,##0.###", "valign": "vcenter",
            })
            summary.merge_range(
                sap_row, 0, sap_row, 1,
                "Total de Tube à scraper sur SAP (Par pièce)", sap_label,
            )
            summary.set_row(sap_row, 32)
            summary.write_number(sap_row, 2, order.sap_tube_quantity, sap_value)
            formula_style = book.add_format({"text_wrap": True, "font_color": "#4C5869"})
            summary.merge_range(
                sap_row + 1, 0, sap_row + 1, 2,
                "(Partie de Smooth tube 16x19 + Smooth tube 16x19) / 740",
                formula_style,
            )
            summary.set_row(sap_row + 1, 30)
            summary.merge_range(
                sap_row + 2, 0, sap_row + 2, 2,
                "Arrondi à l'entier le plus proche, avec majoration dès X,5 (exemple : 1,5 devient 2).",
                formula_style,
            )
            summary.set_row(sap_row + 2, 30)
        return output.getvalue()
