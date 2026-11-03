# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

WEEKDAYS = [
    ("0", "Segunda-feira"),
    ("1", "Terça-feira"),
    ("2", "Quarta-feira"),
    ("3", "Quinta-feira"),
    ("4", "Sexta-feira"),
    ("5", "Sábado"),
    ("6", "Domingo"),
]


class AccountPaymentTermLine(models.Model):
    _inherit = "account.payment.term.line"

    delay_type = fields.Selection(
        selection_add=[("itbr_weekday_of_month", "Dia da semana do mês")],
        ondelete={"itbr_weekday_of_month": "set default"},
    )
    itbr_month_offset = fields.Integer(
        string="Meses depois",
        default=1,
        help="Mês do vencimento contado a partir do mês da fatura (0: o próprio mês).",
    )
    itbr_weekday = fields.Selection(
        string="Dia da semana", selection=WEEKDAYS, default="3"
    )
    itbr_weekday_rank = fields.Integer(
        string="Ordem",
        default=1,
        help="1: a primeira ocorrência do dia da semana no mês; 2: a segunda...",
    )
    itbr_business_day = fields.Boolean(
        string="Só dia útil",
        help="O vencimento nunca cai em fim de semana ou feriado do calendário de "
        "trabalho da empresa: no dia da semana do mês, conta só as ocorrências "
        "úteis; nos demais tipos, passa para o próximo dia útil.",
    )

    @api.constrains("delay_type", "itbr_month_offset", "itbr_weekday_rank")
    def _check_itbr_weekday_of_month(self):
        for line in self.filtered(
            lambda term_line: term_line.delay_type == "itbr_weekday_of_month"
        ):
            if line.itbr_month_offset < 0 or not 1 <= line.itbr_weekday_rank <= 5:
                raise ValidationError(
                    self.env._(
                        "Dia da semana do mês: os meses não podem ser negativos e a "
                        "ordem vai de 1 a 5."
                    )
                )

    def _get_due_date(self, date_ref):
        if self.delay_type == "itbr_weekday_of_month":
            return self._itbr_weekday_of_month(date_ref)
        due_date = super()._get_due_date(date_ref)
        if self.itbr_business_day:
            while not self._itbr_is_business_day(due_date):
                due_date += timedelta(days=1)
        return due_date

    def _itbr_weekday_of_month(self, date_ref):
        """The N-th given weekday (business ones only, if asked) of the due month.

        A rank past the last one of the month keeps counting into the next month.
        """
        self.ensure_one()
        ref = fields.Date.from_string(date_ref) or fields.Date.today()
        day = ref.replace(day=1) + relativedelta(months=self.itbr_month_offset)
        weekday = int(self.itbr_weekday or 0)
        day += timedelta(days=(weekday - day.weekday()) % 7)
        found = 0
        while True:
            if not self.itbr_business_day or self._itbr_is_business_day(day):
                found += 1
                if found == self.itbr_weekday_rank:
                    return day
            day += timedelta(weeks=1)

    def _itbr_is_business_day(self, day):
        """A working day of the company calendar that no public holiday covers."""
        company = self.payment_id.company_id or self.env.company
        calendar = company.resource_calendar_id
        workdays = (
            set(calendar.attendance_ids.mapped("dayofweek"))
            if calendar and calendar.attendance_ids
            else {"0", "1", "2", "3", "4"}
        )
        if str(day.weekday()) not in workdays:
            return False
        # Leaves are stored in UTC: the local noon is inside a holiday of that
        # day and outside one of the day before or after.
        tz = pytz.timezone(calendar.tz or company.partner_id.tz or "UTC")
        noon = (
            tz.localize(datetime.combine(day, time(12)))
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )
        holidays = (
            self.env["resource.calendar.leaves"]
            .sudo()
            .search_count(
                [
                    ("resource_id", "=", False),
                    ("calendar_id", "in", [calendar.id, False]),
                    ("company_id", "in", [company.id, False]),
                    ("date_from", "<=", noon),
                    ("date_to", ">=", noon),
                ],
                limit=1,
            )
        )
        return not holidays
