# Copyright 2026 ITBrasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

# base_import_module adds _call_apps() and _get_industry_categories_from_apps()
# to ir.module.module. Both call requests.post directly to apps.odoo.com
# (bypassing iap_tools.iap_jsonrpc), so they need explicit overrides here.

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


def _is_blocking_enabled(env):
    val = env["ir.config_parameter"].sudo().get_param(
        "itbr_disable_odoo_calls.enabled", "1"
    )
    return val != "0"


class _MockAppsResponse:
    """Minimal fake requests.Response that satisfies the callers in
    base_import_module without hitting the network."""

    def raise_for_status(self):
        pass  # pretend the HTTP call succeeded

    def json(self):
        return {"result": []}


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def _call_apps(self, payload):
        """Override: block outbound request to https://apps.odoo.com."""
        if not _is_blocking_enabled(self.env):
            return super()._call_apps(payload)
        _logger.warning(
            "itbr_disable_odoo_calls: blocked _call_apps request to apps.odoo.com"
        )
        return _MockAppsResponse()

    @api.model
    def _get_industry_categories_from_apps(self):
        """Override: block outbound request to https://apps.odoo.com."""
        if not _is_blocking_enabled(self.env):
            return super()._get_industry_categories_from_apps()
        _logger.warning(
            "itbr_disable_odoo_calls: blocked _get_industry_categories_from_apps "
            "request to apps.odoo.com"
        )
        return []
