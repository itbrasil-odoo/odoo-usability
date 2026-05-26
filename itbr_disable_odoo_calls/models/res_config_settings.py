# Copyright 2026 ITBrasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    itbr_disable_odoo_calls_enabled = fields.Boolean(
        string="Bloquear comunicações com Odoo Enterprise",
        config_parameter="itbr_disable_odoo_calls.enabled",
    )
