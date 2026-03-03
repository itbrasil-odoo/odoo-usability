import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PdfdTemplate(models.Model):
    _name = "pdfd.template"
    _description = "PDF Designer Lite Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    key = fields.Char(string="QWeb t-name", help='Used as <t t-name="...">', copy=False)
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        help="Bind this template to a model so portals can auto-pick it.",
        tracking=True,
    )
    show_portal_fields = fields.Boolean(
        default=True,
        help="Render the fields enviados pelo portal (portal_fields).",
    )
    portal_columns = fields.Selection(
        [
            ("1", "1 column"),
            ("2", "2 columns"),
            ("3", "3 columns"),
        ],
        default="2",
        help="Número de colunas para os campos do portal.",
    )

    # Simple switches instead of a builder UI
    show_logo = fields.Boolean(default=True)
    title_text = fields.Char(default="Document Title")
    title_align = fields.Selection(
        [("left", "Left"), ("center", "Center"), ("right", "Right")], default="center"
    )
    show_header_fields = fields.Boolean(default=True)
    show_table = fields.Boolean(default=True)
    show_totals = fields.Boolean(default=True)
    footer_text = fields.Char(default="Thank you for your business!")
    pdf_view_id = fields.Many2one(
        "ir.ui.view",
        string="Generated View",
        readonly=True,
        copy=False,
        help="QWeb view gerada automaticamente para este template.",
    )

    # Generated XML + Preview
    xml_arch = fields.Text(readonly=True)
    preview_html = fields.Html(sanitize=False, readonly=True)

    # Sample context for preview only
    sample_context = fields.Json(
        default=lambda self: {
            "company": {
                "name": "Odooistic Ltd",
                "logo": "/web/static/img/placeholder.png",
            },
            "doc": {
                "name": "Exemplo",
                "code": "EQP-0001",
                "date": "2025-10-29",
                "amount_total": 0,
            },
            "portal_fields": [
                {
                    "label": "Nome exibido",
                    "technical_name": "display_name",
                    "value": "Exemplo de Nome",
                },
                {
                    "label": "Número de série",
                    "technical_name": "serial_no",
                    "value": "SN-0001",
                },
                {
                    "label": "Data",
                    "technical_name": "date",
                    "value": "2025-10-29",
                },
            ],
            "lines": [],
            "totals": {"untaxed": 0, "tax": 0, "total": 0},
        }
    )

    def _normalized_tname(self):
        import re

        model_key = (
            self.model_id.model.replace(".", "_")
            if self.model_id and self.model_id.id
            else False
        )
        base = (self.key or model_key or f"pdfd_lite_{self.id or 'new'}").strip()
        base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
        # If user typed a simple name, namespace it to avoid collisions
        if "." not in base:
            base = f"pdf_designer_lite.{base}"
        return base

    def action_generate_xml(self):
        for rec in self:
            tname = rec._normalized_tname()
            try:
                columns = int(rec.portal_columns or 2)
            except (TypeError, ValueError):
                columns = 2
            _logger.warning(
                "PDFD: action_generate_xml template id=%s name=%s key=%s columns=%s",
                rec.id,
                rec.name,
                tname,
                columns,
            )
            col_class = {1: "col-12", 2: "col-6", 3: "col-4"}.get(columns, "col-6")
            pieces = [
                f'<t t-name="{tname}">',
                (
                    '<div class="doc" style="font-family:Arial,sans-serif;'
                    'font-size:12px;padding:24px;max-width:900px;margin:0 auto;">'
                ),
            ]

            # ✅ Safe logo expression for dict-based context
            if rec.show_logo:
                pieces.append(
                    '<div class="logo">'
                    "<img t-att-src=\"company and company.get('logo')\" "
                    'style="max-height:64px"/>'
                    "</div>"
                )

            # Title
            if rec.title_text:
                pieces.append(
                    f'<h2 style="text-align:{rec.title_align};margin:12px 0 18px;">'
                    f"{rec.title_text}</h2>"
                )

            # Portal fields grid (preferred path)
            if rec.show_portal_fields:
                pieces.append(
                    '<t t-if="portal_fields">\n'
                    '  <div class="row portal-fields" style="margin-top:12px;'
                    'gap:6px;">\n'
                    '    <t t-foreach="portal_fields" t-as="f">\n'
                    f'      <div class="{col_class} mb-3" '
                    'style="padding:6px 8px;border:1px solid #ddd;'
                    'border-radius:6px;">\n'
                    '        <div style="font-weight:600;margin-bottom:4px;" '
                    "t-esc=\"f.get('label') or f.get('technical_name')\"/>\n"
                    '        <div style="color:#333;" t-esc="f.get(\'value\')"/>\n'
                    "      </div>\n"
                    "    </t>\n"
                    "  </div>\n"
                    "</t>\n"
                    '<t t-else="">\n'
                    '  <t t-set="items" t-value="(doc or {})"/>\n'
                    '  <t t-if="items">\n'
                    "    <ul>\n"
                    '      <t t-foreach="items.items()" t-as="item">\n'
                    '        <li><strong t-esc="item[0]"/>: '
                    '<span t-esc="item[1]"/></li>\n'
                    "      </t>\n"
                    "    </ul>\n"
                    "  </t>\n"
                    '  <t t-else="">\n'
                    "    <em>No fields configured.</em>\n"
                    "  </t>\n"
                    "</t>\n"
                )

            # Footer
            if rec.footer_text:
                pieces.append(
                    f'<div class="footer" '
                    f'style="margin-top:16px;font-size:12px;color:#777">'
                    f"{rec.footer_text}</div>"
                )

            # Close tags
            pieces.append("</div></t>")

            # Save and render
            rec.xml_arch = "\n".join(pieces)
            view = rec._sync_qweb_view(tname)
            rec.preview_html = rec._render_preview(tname)
            rec.pdf_view_id = view.id if view else False

    def _sync_qweb_view(self, tname):
        """Create or update ir.ui.view for this template."""
        View = self.env["ir.ui.view"].sudo()
        model_name = self.model_id.model if self.model_id else False
        view_values = {
            "name": f"PDF Designer Lite - {self.name or tname}",
            "type": "qweb",
            "arch_db": self.xml_arch or f'<t t-name="{tname}"></t>',
            "key": tname,
        }
        if model_name:
            view_values["model"] = model_name

        # Prefer linked view if present
        view = self.pdf_view_id and self.pdf_view_id.sudo()
        if view and view.exists():
            _logger.warning("PDFD: updating linked view id=%s key=%s", view.id, tname)
            view.write(view_values)
        else:
            view = View.search([("key", "=", tname)], limit=1)
            if view:
                _logger.warning(
                    "PDFD: updating view found by key id=%s key=%s", view.id, tname
                )
                view.write(view_values)
            else:
                _logger.warning("PDFD: creating new view for key=%s", tname)
                view = View.create(view_values)

        if hasattr(View, "clear_caches"):
            View.clear_caches()
        return view

    def unlink(self):
        views = self.mapped("pdf_view_id")
        res = super().unlink()
        if views:
            _logger.warning(
                "PDFD: deleting linked views ids=%s after template unlink", views.ids
            )
            views.sudo().unlink()
        return res

    def _render_preview(self, tname=None):
        """Render xml_arch preview safely in Odoo 19."""
        self.ensure_one()
        from odoo import tools

        View = self.env["ir.ui.view"]
        tname = tname or self._normalized_tname()
        arch = self.xml_arch or f'<t t-name="{tname}"/>'

        # Give the transient view its own unique key
        view_key = f"pdf_designer_lite.preview_{self.id}"

        try:
            # Create the transient view record
            view = View.create(
                {
                    "name": f"PDFD Preview {self.id}",
                    "type": "qweb",
                    "arch_db": arch,
                    "key": view_key,
                }
            )

            # Clear caches so Odoo reindexes this transient view
            if hasattr(View, "clear_caches"):
                View.clear_caches()

            # ✅ Render by KEY (which is guaranteed to exist)
            html = View._render_template(view_key, self.sample_context or {})
            return html

        except Exception as e:
            return (
                "<div style='color:red;padding:1em;'>Preview failed: "
                f"{tools.html_escape(str(e))}</div>"
            )

        finally:
            # Cleanup transient view
            try:
                view.sudo().unlink()
            except Exception as e:
                _logger.error("Failed to cleanup transient view: %s", e)

    def action_export_xml(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/pdfd_lite/export/{self.id}",
            "target": "self",
        }

    def action_open_builder(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/pdfd_lite/builder/{self.id}",
            "target": "new",
        }
