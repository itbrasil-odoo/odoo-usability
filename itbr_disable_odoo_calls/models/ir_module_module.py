# Copyright 2026 ITBrasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

# base_import_module adds _call_apps() and _get_industry_categories_from_apps()
# to ir.module.module. Both call requests.post directly to apps.odoo.com
# (bypassing iap_tools.iap_jsonrpc), so they need explicit overrides here.

import logging

from odoo import api, models
from odoo.tools import ormcache

_logger = logging.getLogger(__name__)


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
    @ormcache("payload")
    def _call_apps(self, payload):
        """Override: block outbound request to https://apps.odoo.com."""
        _logger.warning(
            "itbr_disable_odoo_calls: blocked _call_apps request to apps.odoo.com"
        )
        return _MockAppsResponse()

    @api.model
    @ormcache()
    def _get_industry_categories_from_apps(self):
        """Override: block outbound request to https://apps.odoo.com."""
        _logger.warning(
            "itbr_disable_odoo_calls: blocked _get_industry_categories_from_apps "
            "request to apps.odoo.com"
        )
        return []
