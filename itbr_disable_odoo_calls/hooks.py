# Copyright 2026 ITBrasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

_logger = logging.getLogger(__name__)
_BLOCK_MESSAGE = "itbr_disable_odoo_calls: blocked outbound request to %s"

# IAP endpoints that must ALWAYS be allowed (Avalara Brasil proxy)
_ALLOWED_IAP_HOSTS = (
    "l10n-br-avatax.api.odoo.com",
    "l10n-br-avatax.test.odoo.com",
)


def _is_blocking_enabled():
    """Return True if blocking is enabled. Defaults to True when no DB context."""
    try:
        from odoo.http import request as http_req
        if http_req and hasattr(http_req, "env") and http_req.env:
            val = http_req.env["ir.config_parameter"].sudo().get_param(
                "itbr_disable_odoo_calls.enabled", "1"
            )
            return val != "0"
    except RuntimeError:
        pass
    try:
        from odoo.api import Environment

        local_envs = getattr(Environment._local, "environments", None)
        if local_envs:
            env = list(local_envs)[-1]
            val = env["ir.config_parameter"].sudo().get_param(
                "itbr_disable_odoo_calls.enabled", "1"
            )
            return val != "0"
    except Exception:
        pass
    return True  # sem contexto de BD: bloquear por segurança


def post_load():
    """Monkey-patch iap_tools.iap_jsonrpc to block all IAP HTTP calls.

    Avalara Brasil (l10n_br_avatax_proxy) is always exempted.
    All other IAP calls are blocked when the system parameter
    itbr_disable_odoo_calls.enabled is '1' (default).
    """
    try:
        from odoo import _
        from odoo.exceptions import AccessError
        from odoo.addons.iap.tools import iap_tools

        _original_iap_jsonrpc = iap_tools.iap_jsonrpc

        def _iap_jsonrpc_disabled(url, method="call", params=None, timeout=15):
            # Avalara Brasil: always allow regardless of setting
            if any(host in url for host in _ALLOWED_IAP_HOSTS):
                return _original_iap_jsonrpc(
                    url, method=method, params=params, timeout=timeout
                )
            if not _is_blocking_enabled():
                return _original_iap_jsonrpc(
                    url, method=method, params=params, timeout=timeout
                )
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
