# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""A conta a receber padrão e a reclassificação do que já foi postado."""

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestReceivableSetup(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env["account.account"]
        # A conta técnica em que as faturas caem quando o ir.default aponta para
        # o lugar errado — o defeito que este assistente conserta.
        cls.transit = Account.create(
            {
                "name": "Numerários em Trânsito",
                "code": "1.01.01.04.01",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_ids": [(6, 0, cls.company_data["company"].ids)],
            }
        )
        cls.clientes = Account.create(
            {
                "name": "Clientes",
                "code": "1.1.2.01.000001",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_ids": [(6, 0, cls.company_data["company"].ids)],
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Cliente de teste"})
        cls.partner.with_company(
            cls.company_data["company"]
        ).property_account_receivable_id = cls.transit

    def _wizard(self):
        return self.env["itbr.finance.receivable.setup"].create(
            {"company_id": self.company_data["company"].id}
        )

    def _invoice(self):
        """Fatura criada direto, sem o helper que passa pelo formulário.

        `init_invoice` monta a fatura via Form, e o Form cobra os campos que a
        localização latino-americana marca como obrigatórios na view — que não
        têm nada a ver com o que se testa aqui.
        """
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.context_today(self.env["account.move"]),
                "journal_id": self.company_data["default_journal_sale"].id,
                "invoice_line_ids": [
                    (0, 0, {
                        "name": "produto de teste",
                        "quantity": 1,
                        "price_unit": 100.0,
                        "tax_ids": [],
                        "account_id": self.company_data["default_account_revenue"].id,
                    })
                ],
            }
        )
        invoice.action_post()
        return invoice

    def test_suggests_the_only_clientes_account(self):
        self.assertEqual(self._wizard().account_id, self.clientes)

    def test_suggests_nothing_when_ambiguous(self):
        self.env["account.account"].create(
            {
                "name": "CLIENTES",
                "code": "1.1.2.01.000099",
                "account_type": "asset_receivable",
                "company_ids": [(6, 0, self.company_data["company"].ids)],
            }
        )
        # Duas candidatas: escolher por conta própria mandaria todas as faturas
        # seguintes para uma conta possivelmente errada.
        self.assertFalse(self._wizard().account_id)

    def test_apply_sets_the_company_default(self):
        wizard = self._wizard()
        wizard.reclassify = False
        wizard.action_apply()

        self.assertEqual(
            self.env["ir.default"]._get(
                "res.partner",
                "property_account_receivable_id",
                company_id=self.company_data["company"].id,
            ),
            self.clientes.id,
        )

    def test_apply_moves_the_open_line(self):
        invoice = self._invoice()
        term = invoice.line_ids.filtered(lambda line: line.display_type == "payment_term")
        self.assertEqual(term.account_id, self.transit)

        wizard = self._wizard()
        self.assertEqual(wizard.line_count, 1)
        wizard.action_apply()

        self.assertEqual(term.account_id, self.clientes)
        # Valor, parceiro e situação não são assunto da reclassificação.
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.amount_residual, invoice.amount_total)
        self.assertAlmostEqual(sum(invoice.line_ids.mapped("balance")), 0.0, places=2)

    def test_apply_leaves_reconciled_lines_alone(self):
        invoice = self._invoice()
        term = invoice.line_ids.filtered(lambda line: line.display_type == "payment_term")

        counterpart = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.company_data["default_journal_misc"].id,
                "line_ids": [
                    (0, 0, {
                        "account_id": self.transit.id,
                        "partner_id": self.partner.id,
                        "credit": invoice.amount_total,
                    }),
                    (0, 0, {
                        "account_id": self.company_data["default_account_revenue"].id,
                        "debit": invoice.amount_total,
                    }),
                ],
            }
        )
        counterpart.action_post()
        (term + counterpart.line_ids.filtered(
            lambda line: line.account_id == self.transit
        )).reconcile()

        wizard = self._wizard()
        self.assertEqual(wizard.line_count, 0)
        wizard.action_apply()

        # Trocar a conta de uma linha conciliada desfaz a baixa: fica de fora.
        self.assertEqual(term.account_id, self.transit)

    def test_apply_honours_the_batch_limit(self):
        invoices = self.env["account.move"].union(*(self._invoice() for _ in range(3)))
        terms = invoices.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )

        wizard = self._wizard()
        wizard.batch_size = 1
        wizard.action_apply()

        self.assertEqual(len(terms.filtered(lambda t: t.account_id == self.clientes)), 1)
        self.assertEqual(wizard.remaining_moves, 2)
        self.assertTrue(wizard.can_continue)

        wizard.action_continue()
        wizard.action_continue()

        self.assertEqual(terms.account_id, self.clientes)
        self.assertFalse(wizard.remaining_moves)
        self.assertFalse(wizard.can_continue)

    def test_apply_ignores_manual_entries(self):
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.company_data["default_journal_misc"].id,
                "line_ids": [
                    (0, 0, {
                        "account_id": self.transit.id,
                        "partner_id": self.partner.id,
                        "debit": 50.0,
                    }),
                    (0, 0, {
                        "account_id": self.company_data["default_account_revenue"].id,
                        "credit": 50.0,
                    }),
                ],
            }
        )
        entry.action_post()

        wizard = self._wizard()
        wizard.action_apply()

        # Lançamento manual parado em conta de cliente é problema de
        # conciliação, e o painel já o reporta à parte.
        self.assertEqual(
            entry.line_ids.filtered(lambda line: line.partner_id).account_id,
            self.transit,
        )
