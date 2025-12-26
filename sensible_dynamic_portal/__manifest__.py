# Powered by Sensible Consulting Services
# © 2025 Sensible Consulting Services (<https://sensiblecs.com/>)
# © 2025 IT Brasil (<https://itbrasil.com.br/>)
{
    "name": "Dynamic Portal",
    "version": "19.0.1.0.0",
    "summary": """Dynamic portals offer customizable""",
    "category": "Extra Tools",
    "author": "Sensible Consulting Services, IT Brasil",
    "maintainers": ["renanteixeira"],
    "website": "https://github.com/itbrasil-odoo/odoo-usability",
    "license": "AGPL-3",
    "depends": ["portal", "pdf_designer_lite"],
    "data": [
        "security/ir.model.access.csv",
        "views/sbl_dynamic_portal_view.xml",
        "views/sbl_portal_template.xml",
        "views/sbl_menu_view.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
