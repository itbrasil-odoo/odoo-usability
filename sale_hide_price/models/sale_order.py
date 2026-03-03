# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    show_portal_values = fields.Boolean(
        default=False,
        help="If enabled, product values are displayed on the customer portal and PDF.",
    )
    show_portal_so_total_amount = fields.Boolean(
        string="Show Portal Total Amount",
        default=True,
        help="If enabled, total amounts are displayed on the customer portal and PDF.",
    )
