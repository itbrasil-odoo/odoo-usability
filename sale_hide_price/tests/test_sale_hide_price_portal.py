# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import html

from odoo.fields import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.sale.tests.common import SaleCommon


@tagged("sale_hide_price", "post_install", "-at_install")
class TestSaleHidePricePortal(HttpCase, SaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_portal = cls._create_new_portal_user()
        cls.visible_quote = cls._create_portal_order(
            state="sent",
            show_portal_values=True,
            show_portal_so_total_amount=True,
        )
        cls.hidden_quote = cls._create_portal_order(
            state="sent",
            show_portal_values=False,
            show_portal_so_total_amount=False,
        )
        cls.visible_order = cls._create_portal_order(
            state="sale",
            show_portal_values=True,
            show_portal_so_total_amount=True,
        )
        cls.hidden_order = cls._create_portal_order(
            state="sale",
            show_portal_values=False,
            show_portal_so_total_amount=False,
        )

    @classmethod
    def _create_portal_order(
        cls, *, state, show_portal_values, show_portal_so_total_amount
    ):
        order = cls.env["sale.order"].create(
            {
                "partner_id": cls.user_portal.partner_id.id,
                "show_portal_values": show_portal_values,
                "show_portal_so_total_amount": show_portal_so_total_amount,
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 2.0,
                            "discount": 10.0,
                        }
                    )
                ],
            }
        )
        if state == "sent":
            order.action_quotation_sent()
        elif state == "sale":
            order.action_confirm()
        order._portal_ensure_token()
        return order

    def _parse_html(self, response):
        return html.fromstring(response.content)

    def _find_row_by_name(self, tree, name):
        for row in tree.xpath("//tr[.//a]"):
            labels = [
                label.strip() for label in row.xpath(".//a/text()") if label.strip()
            ]
            if name in labels:
                return row
        self.fail(f"Row for {name} not found")

    def test_hidden_quote_page_hides_amount_nodes_for_portal_user(self):
        self.authenticate(self.user_portal.login, self.user_portal.login)

        response = self.url_open(f"/my/orders/{self.hidden_quote.id}")
        tree = self._parse_html(response)
        sidebar = tree.xpath("//*[contains(@class, 'o_portal_sale_sidebar')]")[0]

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(sidebar.get("data-order-amount-total"))
        self.assertFalse(tree.xpath("//*[@id='product_unit_price_header']"))
        self.assertFalse(tree.xpath("//*[@id='product_discount_header']"))
        self.assertFalse(tree.xpath("//*[@id='subtotal_header']"))
        self.assertFalse(tree.xpath("//table[@name='sale_order_totals_table']"))

    def test_hidden_quote_page_is_public_with_token(self):
        self.authenticate(None, None)

        response = self.url_open(self.hidden_quote.get_portal_url())
        tree = self._parse_html(response)
        sidebar = tree.xpath("//*[contains(@class, 'o_portal_sale_sidebar')]")[0]

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(sidebar.get("data-order-amount-total"))
        self.assertFalse(tree.xpath("//*[@id='subtotal_header']"))

    def test_quotes_list_hides_totals_per_record(self):
        self.authenticate(self.user_portal.login, self.user_portal.login)

        response = self.url_open("/my/quotes")
        tree = self._parse_html(response)
        hidden_row = self._find_row_by_name(tree, self.hidden_quote.name)
        visible_row = self._find_row_by_name(tree, self.visible_quote.name)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(tree.xpath("//th[normalize-space()='Total']"))
        self.assertEqual(
            hidden_row.xpath("./td[last()]")[0].text_content().strip(), "-"
        )
        self.assertNotEqual(
            visible_row.xpath("./td[last()]")[0].text_content().strip(), "-"
        )

    def test_orders_list_hides_totals_per_record(self):
        self.authenticate(self.user_portal.login, self.user_portal.login)

        response = self.url_open("/my/orders")
        tree = self._parse_html(response)
        hidden_row = self._find_row_by_name(tree, self.hidden_order.name)
        visible_row = self._find_row_by_name(tree, self.visible_order.name)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(tree.xpath("//th[@name='order_total']"))
        self.assertEqual(
            hidden_row.xpath("./td[last()]")[0].text_content().strip(), "-"
        )
        self.assertNotEqual(
            visible_row.xpath("./td[last()]")[0].text_content().strip(), "-"
        )

    def test_hidden_quote_pdf_is_available(self):
        self.authenticate(None, None)

        response = self.url_open(
            self.hidden_quote.get_portal_url(report_type="pdf"),
            allow_redirects=False,
        )

        self.assertEqual(response.status_code, 200)
