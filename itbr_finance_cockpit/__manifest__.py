# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Cockpit Financeiro",
    "summary": "Telas simples de financeiro para sócios e administrativo",
    "version": "19.0.1.0.0",
    "author": "IT Brasil",
    "website": "https://github.com/itbrasil-odoo",
    "license": "LGPL-3",
    "category": "Accounting/Accounting",
    "depends": [
        "account",
    ],
    "data": [
        "security/finance_cockpit_security.xml",
        "security/ir.model.access.csv",
        # as views precisam existir antes das ações que as referenciam
        "views/account_move_views.xml",
        "wizard/finance_receivable_setup_views.xml",
        "views/finance_cockpit_actions.xml",
        "views/finance_cockpit_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "itbr_finance_cockpit/static/src/components/**/*.js",
            "itbr_finance_cockpit/static/src/components/**/*.xml",
            "itbr_finance_cockpit/static/src/components/**/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
