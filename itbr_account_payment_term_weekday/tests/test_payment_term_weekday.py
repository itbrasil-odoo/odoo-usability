# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import date, datetime, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPaymentTermWeekday(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env.company.resource_calendar_id
        cls.calendar.tz = "America/Sao_Paulo"

    def term(self, **line):
        line.setdefault("value", "percent")
        line.setdefault("value_amount", 100)
        return self.env["account.payment.term"].create(
            {"name": "Teste", "line_ids": [Command.create(line)]}
        )

    def due(self, term, day):
        return term.line_ids._get_due_date(day)

    def holiday(self, day):
        # 00:00 to 23:59 in São Paulo (UTC-3), stored in UTC.
        self.env["resource.calendar.leaves"].create(
            {
                "name": "Feriado",
                "calendar_id": self.calendar.id,
                "date_from": datetime(day.year, day.month, day.day, 3),
                "date_to": datetime(day.year, day.month, day.day, 3)
                + timedelta(hours=23, minutes=59, seconds=59),
            }
        )

    def first_thursday(self, **values):
        values = {
            "delay_type": "itbr_weekday_of_month",
            "itbr_month_offset": 2,
            "itbr_weekday": "3",
            "itbr_weekday_rank": 1,
            "itbr_business_day": True,
            **values,
        }
        return self.term(**values)

    def test_first_thursday_two_months_later(self):
        term = self.first_thursday()
        self.assertEqual(self.due(term, date(2026, 10, 1)), date(2026, 12, 3))
        self.assertEqual(self.due(term, date(2026, 9, 1)), date(2026, 11, 5))
        self.assertEqual(self.due(term, date(2026, 9, 30)), date(2026, 11, 5))

    def test_holiday_moves_to_the_next_business_thursday(self):
        term = self.first_thursday()
        self.holiday(date(2026, 12, 3))
        self.assertEqual(self.due(term, date(2026, 10, 1)), date(2026, 12, 10))

    def test_holiday_of_the_day_before_is_not_this_day(self):
        term = self.first_thursday()
        self.holiday(date(2026, 12, 2))
        self.assertEqual(self.due(term, date(2026, 10, 1)), date(2026, 12, 3))

    def test_without_business_day_the_holiday_counts(self):
        term = self.first_thursday(itbr_business_day=False)
        self.holiday(date(2026, 12, 3))
        self.assertEqual(self.due(term, date(2026, 10, 1)), date(2026, 12, 3))

    def test_other_types_roll_to_the_next_business_day(self):
        term = self.term(
            delay_type="days_after_end_of_next_month",
            nb_days=20,
            itbr_business_day=True,
        )
        # 20/12/2026 is a Sunday.
        self.assertEqual(self.due(term, date(2026, 10, 1)), date(2026, 12, 21))
        self.assertEqual(self.due(term, date(2026, 11, 3)), date(2027, 1, 20))

    def test_standard_types_are_unchanged(self):
        term = self.term(delay_type="days_after_end_of_next_month", nb_days=20)
        self.assertEqual(self.due(term, date(2026, 10, 1)), date(2026, 12, 20))

    def test_invoice_gets_the_due_date(self):
        partner = self.env["res.partner"].create({"name": "Cliente"})
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": date(2026, 10, 1),
                "invoice_payment_term_id": self.first_thursday().id,
                "invoice_line_ids": [
                    Command.create({"name": "Locação", "price_unit": 100.0})
                ],
            }
        )
        self.assertEqual(invoice.invoice_date_due, date(2026, 12, 3))

    def test_rank_out_of_range_is_refused(self):
        with self.assertRaises(ValidationError):
            self.first_thursday(itbr_weekday_rank=6)
