# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Prazo de pagamento por dia da semana e dia útil",
    "summary": "Vencimento na N-ésima quinta-feira (ou outro dia) útil do mês e "
    "vencimento adiado para o próximo dia útil",
    "version": "19.0.1.0.0",
    "author": "IT Brasil",
    "website": "https://github.com/itbrasil-odoo/odoo-usability",
    "license": "LGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account", "resource"],
    "data": ["views/account_payment_term_views.xml"],
    "installable": True,
    "application": False,
}
