# Copyright 2026 ITBrasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

# publisher_warranty.contract._get_sys_logs calls requests.post directly
# to http://services.odoo.com/publisher-warranty/ — it does NOT go through
# iap_tools.iap_jsonrpc, so it needs its own model-level override.

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


def _is_blocking_enabled(env):
    val = env["ir.config_parameter"].sudo().get_param(
        "itbr_disable_odoo_calls.enabled", "1"
    )
    return val != "0"


class PublisherWarrantyContract(models.AbstractModel):
    _inherit = "publisher_warranty.contract"

    @api.model
    def _get_sys_logs(self):
        """Override: skip the HTTP call to services.odoo.com and return a
        minimal valid response so that update_notification() can complete
        without errors.
        """
        if not _is_blocking_enabled(self.env):
            return super()._get_sys_logs()
        _logger.info(
            "itbr_disable_odoo_calls: blocked _get_sys_logs call to services.odoo.com"
        )
        return {"messages": [], "enterprise_info": {}}

    def update_notification(self, cron_mode=True):
        """Override: skip all remote communication and return success."""
        if not _is_blocking_enabled(self.env):
            return super().update_notification(cron_mode=cron_mode)
        _logger.info(
            "itbr_disable_odoo_calls: blocked update_notification call "
            "to services.odoo.com"
        )
        return True
