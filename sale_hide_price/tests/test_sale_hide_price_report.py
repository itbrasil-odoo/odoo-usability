# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import html

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.sale.tests.common import SaleCommon


@tagged("sale_hide_price")
class TestSaleHidePriceReport(SaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "show_portal_values": True,
                "show_portal_so_total_amount": True,
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

    def _render_report(self):
        content = self.env["ir.actions.report"]._render_qweb_html(
            "sale.action_report_saleorder", self.report_order.ids
        )[0]
        return html.fromstring(content)

    def _assert_report_nodes(
        self,
        tree,
        *,
        has_price_unit,
        has_discount,
        has_subtotal,
        has_total_summary,
    ):
        self.assertEqual(bool(tree.xpath("//*[@name='th_priceunit']")), has_price_unit)
        self.assertEqual(bool(tree.xpath("//*[@name='th_discount']")), has_discount)
        self.assertEqual(bool(tree.xpath("//*[@name='th_subtotal']")), has_subtotal)
        self.assertEqual(
            bool(tree.xpath("//*[@name='so_total_summary']")), has_total_summary
        )

    def test_default_values(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertFalse(order.show_portal_values)
        self.assertTrue(order.show_portal_so_total_amount)

    def test_report_with_all_values_visible(self):
        tree = self._render_report()
        self._assert_report_nodes(
            tree,
            has_price_unit=True,
            has_discount=True,
            has_subtotal=True,
            has_total_summary=True,
        )

    def test_report_hides_line_values(self):
        self.report_order.show_portal_values = False

        tree = self._render_report()
        self._assert_report_nodes(
            tree,
            has_price_unit=False,
            has_discount=False,
            has_subtotal=False,
            has_total_summary=True,
        )

    def test_report_hides_total_summary(self):
        self.report_order.show_portal_values = True
        self.report_order.show_portal_so_total_amount = False

        tree = self._render_report()
        self._assert_report_nodes(
            tree,
            has_price_unit=True,
            has_discount=True,
            has_subtotal=True,
            has_total_summary=False,
        )

    def test_report_hides_line_values_and_total_summary(self):
        self.report_order.write(
            {
                "show_portal_values": False,
                "show_portal_so_total_amount": False,
            }
        )

        tree = self._render_report()
        self._assert_report_nodes(
            tree,
            has_price_unit=False,
            has_discount=False,
            has_subtotal=False,
            has_total_summary=False,
        )
