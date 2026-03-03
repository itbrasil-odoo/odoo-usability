# Copyright 2026 ITBrasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

# post_load hook: runs once at server startup when Python loads this module.
# This is the right place to patch module-level functions that are not
# model methods (like iap_tools.iap_jsonrpc).

import logging

_logger = logging.getLogger(__name__)

_BLOCK_MESSAGE = "itbr_disable_odoo_calls: blocked outbound request to %s"


def post_load():
    """Monkey-patch iap_tools.iap_jsonrpc to block all IAP HTTP calls.

    iap_tools.iap_jsonrpc is the single central function used by every
    IAP-based service (SMS, snailmail, partner autocomplete, CRM lead
    mining, html_editor media library, account info fetching, etc.).
    Replacing it here ensures they all silently fail before touching the
    network, regardless of which addon triggers the call.
    """
    try:
        from odoo import _
        from odoo.exceptions import AccessError

        from odoo.addons.iap.tools import iap_tools

        _original_iap_jsonrpc = iap_tools.iap_jsonrpc  # kept for reference

        def _iap_jsonrpc_disabled(url, method="call", params=None, timeout=15):
            _logger.warning(_BLOCK_MESSAGE, url)
            raise AccessError(
                _("IAP communication is disabled by itbr_disable_odoo_calls.")  # pylint: disable=prefer-env-translation
            )

        iap_tools.iap_jsonrpc = _iap_jsonrpc_disabled
        _logger.info(
            "itbr_disable_odoo_calls: iap_tools.iap_jsonrpc successfully patched."
        )
    except Exception:
        _logger.exception(
            "itbr_disable_odoo_calls: failed to patch iap_tools.iap_jsonrpc."
        )
