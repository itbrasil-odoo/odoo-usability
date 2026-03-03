# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Sale Hide Price",
    "summary": "Hide sale prices on the portal and PDF",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "author": "IT Brasil, Renan Teixeira",
    "maintainers": ["renanteixeira"],
    "website": "https://github.com/itbrasil-odoo/odoo-usability",
    "license": "AGPL-3",
    "depends": ["sale"],
    "data": [
        "views/sale_order_views.xml",
        "views/sale_portal_templates.xml",
        "report/sale_report_templates.xml",
    ],
    "installable": True,
}
