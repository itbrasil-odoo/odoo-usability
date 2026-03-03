from odoo import http
from odoo.http import request


class PdfdBuilderController(http.Controller):
    @http.route(
        "/pdfd_lite/builder/<int:template_id>",
        type="http",
        auth="user",
        website=True,
    )
    def builder(self, template_id, **kwargs):
        template = request.env["pdfd.template"].sudo().browse(template_id)
        if not template.exists():
            return request.not_found()
        body = template.xml_arch or ""
        sample_ctx = template.sample_context or {}
        return request.render(
            "pdf_designer_lite.pdfd_builder",
            {
                "template": template,
                "body": body,
                "sample_ctx": sample_ctx,
            },
        )

    @http.route(
        "/pdfd_lite/builder/<int:template_id>/save",
        type="jsonrpc",
        auth="user",
        csrf=False,
    )
    def builder_save(self, template_id, html, **kwargs):
        template = request.env["pdfd.template"].sudo().browse(template_id)
        if not template.exists():
            return {"error": "Template not found"}
        template.write({"xml_arch": html})
        template.action_generate_xml()
        return {"status": "ok"}
