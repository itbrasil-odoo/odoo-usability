# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Os sinais de que a posição do painel é de outra época."""

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSettlementHealth(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.today = fields.Date.context_today(cls.env["account.move"])
        cls.cockpit = cls.env["itbr.finance.cockpit"].with_context(
            allowed_company_ids=cls.company.ids
        )

    def _statement_line(self, journal, date, reconciled=False):
        line = self.env["account.bank.statement.line"].create(
            {
                "journal_id": journal.id,
                "payment_ref": "extrato",
                "amount": 100.0,
                "date": date,
            }
        )
        if reconciled:
            line.move_id.line_ids.filtered(
                lambda aml: aml.account_id == journal.suspense_account_id
            ).account_id = self.company_data["default_account_revenue"]
            line.move_id.action_post()
        return line

    def test_journal_without_statement_is_flagged(self):
        health = self.cockpit._get_settlement_health()
        flagged = {stale["journal_id"] for stale in health["stale_journals"]}
        self.assertIn(self.company_data["default_journal_bank"].id, flagged)
        self.assertFalse(health["reliable"])

    def test_recent_statement_clears_the_journal(self):
        journal = self.company_data["default_journal_bank"]
        self._statement_line(journal, self.today)

        health = self.cockpit._get_settlement_health()
        flagged = {stale["journal_id"] for stale in health["stale_journals"]}
        self.assertNotIn(journal.id, flagged)

    def test_old_statement_keeps_the_journal_flagged(self):
        journal = self.company_data["default_journal_bank"]
        old = self.today - relativedelta(months=6)
        self._statement_line(journal, old)

        health = self.cockpit._get_settlement_health()
        stale = {s["journal_id"]: s for s in health["stale_journals"]}
        self.assertIn(journal.id, stale)
        self.assertEqual(stale[journal.id]["last_statement"], old)

    def test_recent_journal_does_not_hide_an_old_one(self):
        """O sinal é por diário justamente por isto.

        Uma linha de caixa de ontem convivendo com bancos parados há meses
        fazia a medida global dizer que estava tudo em dia.
        """
        fresh = self.company_data["default_journal_cash"]
        stale_journal = self.company_data["default_journal_bank"]
        self._statement_line(fresh, self.today)
        self._statement_line(stale_journal, self.today - relativedelta(months=6))

        flagged = {
            stale["journal_id"]
            for stale in self.cockpit._get_settlement_health()["stale_journals"]
        }
        self.assertIn(stale_journal.id, flagged)
        self.assertNotIn(fresh.id, flagged)

    def test_pending_statement_lines_are_counted(self):
        journal = self.company_data["default_journal_bank"]
        self._statement_line(journal, self.today)

        health = self.cockpit._get_settlement_health()
        self.assertEqual(health["pending_statement_lines"], 1)
        self.assertFalse(health["reliable"])

    def test_overview_carries_the_health(self):
        self.assertIn("settlement_health", self.cockpit.get_overview())
