# Copyright 2026 ITBrasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Disable Odoo External Calls",
    "summary": "Blocks all outbound communication with *.odoo.com servers",
    "version": "19.0.1.0.0",
    "author": "IT Brasil",
    "website": "https://github.com/itbrasil-odoo/odoo-usability",
    "license": "LGPL-3",
    "category": "Technical",
    "depends": [
        "base",
        "mail",
        "iap",
        "base_import_module",
    ],
    "data": [],
    "demo": [],
    "installable": True,
    "auto_install": False,
    "post_load": "post_load",
    "application": False,
}
