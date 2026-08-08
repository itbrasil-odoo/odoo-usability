# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Serviço de dados do cockpit financeiro.

Tudo aqui é consultado com as empresas ATIVAS do usuário (`self.env.companies`),
nunca com sudo. Duas consequências deliberadas:

* as regras multi-empresa do Odoo continuam valendo, então a Andrada Magela —
  que está na mesma base mas não pertence ao Grupo Dedicata — só aparece para
  quem realmente tem acesso a ela;
* o seletor de empresas do topo da tela funciona como filtro natural do painel.
"""

from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# Acima disso, a diferença entre o saldo do extrato e o saldo contábil do
# diário é tratada como divergência de conciliação e vai para a tela.
RECONCILIATION_TOLERANCE = 0.01

# "A receber" e "a pagar" contam apenas documentos comerciais.
#
# Motivo medido nesta base: havia 24 lançamentos manuais (move_type 'entry')
# em conta de fornecedor somando +57.444,40, com sinal invertido em relação às
# contas de verdade. Somados junto, viravam o sinal do total e o painel dizia
# que o grupo tinha a RECEBER de fornecedores. Lançamento manual não conciliado
# é problema de conciliação, não é conta a pagar — então vai para um aviso
# separado, em vez de poluir o número que o sócio lê.
RECEIVABLE_TYPES = ("out_invoice", "out_refund", "out_receipt")
PAYABLE_TYPES = ("in_invoice", "in_refund", "in_receipt")

# Extrato mais velho que isto significa que a posição da tela é de outra época.
STALE_STATEMENT_DAYS = 30

# Janela para julgar se a operação está de fato dando baixa nos títulos.
SETTLEMENT_WINDOW_DAYS = 90


class FinanceCockpit(models.AbstractModel):
    _name = "itbr.finance.cockpit"
    _description = "Serviço de dados do cockpit financeiro"

    # ------------------------------------------------------------------
    # Blocos de dados
    # ------------------------------------------------------------------

    @api.model
    def _open_items_domain(self, account_type):
        return [
            ("account_id.account_type", "=", account_type),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("company_id", "in", self.env.companies.ids),
        ]

    @api.model
    def _get_open_items(self, account_type, move_types):
        """Linhas em aberto de documentos comerciais de um tipo de conta.

        Devolve [{id, due, amount, company}]. Usa o residual em moeda da
        empresa, que é o que de fato falta entrar ou sair.
        """
        lines = self.env["account.move.line"].search_read(
            self._open_items_domain(account_type) + [("move_id.move_type", "in", move_types)],
            ["date_maturity", "amount_residual", "company_id"],
        )
        today = fields.Date.context_today(self)
        return [
            {
                "id": line["id"],
                "due": line["date_maturity"] or today,
                "amount": line["amount_residual"],
                "company": line["company_id"][0],
            }
            for line in lines
            if line["amount_residual"]
        ]

    @api.model
    def _receivable_channels(self):
        """De quem, quando e se ainda entra — para o que não vem do cliente.

        O painel não sabe o que é Shopee nem o que é borderô, e não deve saber:
        quem instala o canal é que devolve a sua fatia aqui. Cada item traz as
        linhas que são suas, a data em que o dinheiro realmente chega (o
        vencimento da nota não diz nada quando quem paga é a plataforma) e se
        ainda conta como entrada futura — um título já antecipado não conta,
        porque o caixa entrou na antecipação, e somá-lo de novo faria a
        projeção prometer o mesmo dinheiro duas vezes.

        :return: [{code, label, line_ids, expected_dates, in_flow}]
        """
        return []

    @api.model
    def _split_receivables(self, items):
        """Reparte os títulos entre os canais e o que sobra é cliente direto."""
        channels = self._receivable_channels()
        claimed = {}
        for channel in channels:
            for line_id in channel["line_ids"]:
                claimed[line_id] = channel

        buckets = {channel["code"]: [] for channel in channels}
        direct = []
        for item in items:
            channel = claimed.get(item["id"])
            if channel is None:
                direct.append(item)
            else:
                expected = channel.get("expected_dates", {}).get(item["id"])
                buckets[channel["code"]].append({**item, "due": expected or item["due"]})
        return direct, channels, buckets

    @api.model
    def _get_unreconciled_entries(self):
        """Lançamentos manuais parados em contas de cliente/fornecedor.

        Não entram no 'a receber'/'a pagar' porque não são documento comercial,
        mas distorcem a posição real — então são reportados à parte.
        """
        result = []
        for account_type, label in (
            ("asset_receivable", "cliente"),
            ("liability_payable", "fornecedor"),
        ):
            groups = self.env["account.move.line"]._read_group(
                self._open_items_domain(account_type) + [("move_id.move_type", "=", "entry")],
                aggregates=["amount_residual:sum", "__count"],
            )
            total, count = groups[0] if groups else (0.0, 0)
            if count:
                result.append({"scope": label, "count": count, "amount": total or 0.0})
        return result

    @api.model
    def _get_cash_positions(self):
        """Saldo de caixa por diário, pelo extrato e pela contabilidade.

        O saldo do EXTRATO é o que o cockpit mostra como "caixa hoje": é o que o
        banco diz. O saldo CONTÁBIL entra só para expor divergência de
        conciliação — esconder isso daria uma falsa sensação de segurança.
        """
        journals = self.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "in", self.env.companies.ids)]
        )
        if not journals:
            return []

        running = journals._get_journal_dashboard_bank_running_balance()

        accounts = journals.default_account_id
        booked = defaultdict(float)
        if accounts:
            groups = self.env["account.move.line"]._read_group(
                [
                    ("account_id", "in", accounts.ids),
                    ("parent_state", "=", "posted"),
                    ("company_id", "in", self.env.companies.ids),
                ],
                groupby=["account_id"],
                aggregates=["balance:sum"],
            )
            booked = {account.id: total for account, total in groups}

        positions = []
        for journal in journals:
            _has_statement, statement_balance = running.get(journal.id, (False, 0.0))
            account_balance = booked.get(journal.default_account_id.id, 0.0)
            positions.append(
                {
                    "journal_id": journal.id,
                    "journal": journal.name,
                    "company": journal.company_id.name,
                    "statement_balance": statement_balance,
                    "account_balance": account_balance,
                    "gap": account_balance - statement_balance,
                }
            )
        return positions

    @api.model
    def _get_settlement_health(self):
        """O quanto a posição desta tela reflete mesmo o banco.

        Três medidas, nenhuma opinião: até quando o extrato foi importado,
        quantas linhas de extrato seguem sem conciliar e quantos recebimentos
        foram registrados na janela. Um painel que soma títulos em aberto sem
        avisar que ninguém dá baixa neles mente com número exato — e é sempre
        na primeira abertura que alguém percebe.
        """
        companies = self.env.companies.ids
        today = fields.Date.context_today(self)
        cutoff = today - relativedelta(days=STALE_STATEMENT_DAYS)

        journals = self.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "in", companies)]
        )
        # A data do extrato mora no lançamento: em account.bank.statement.line
        # ela é campo delegado (_inherits) e não dá para agregar.
        #
        # E a medida é POR DIÁRIO de propósito. Nesta base, uma única linha de
        # caixa de julho convivia com bancos parados desde agosto do ano
        # anterior: olhar o extrato mais recente do grupo dizia que estava tudo
        # em dia.
        groups = self.env["account.move"]._read_group(
            [("journal_id", "in", journals.ids), ("statement_line_id", "!=", False)],
            groupby=["journal_id"],
            aggregates=["date:max"],
        )
        last_by_journal = {journal.id: date for journal, date in groups}

        stale = [
            {
                "journal_id": journal.id,
                "journal": journal.name,
                "company": journal.company_id.name,
                "last_statement": last_by_journal.get(journal.id) or False,
            }
            for journal in journals
            if not last_by_journal.get(journal.id)
            or last_by_journal[journal.id] < cutoff
        ]

        pending = self.env["account.bank.statement.line"].search_count(
            [("company_id", "in", companies), ("is_reconciled", "=", False)]
        )
        settlements = self.env["account.payment"].search_count(
            [
                ("company_id", "in", companies),
                ("date", ">=", today - relativedelta(days=SETTLEMENT_WINDOW_DAYS)),
            ]
        )

        return {
            "stale_journals": stale,
            "pending_statement_lines": pending,
            "recent_settlements": settlements,
            "window_days": SETTLEMENT_WINDOW_DAYS,
            "reliable": not stale and not pending,
        }

    # ------------------------------------------------------------------
    # API chamada pelo frontend
    # ------------------------------------------------------------------

    @api.model
    def get_overview(self):
        """KPIs consolidados das empresas ativas do usuário."""
        today = fields.Date.context_today(self)
        receivables = self._get_open_items("asset_receivable", RECEIVABLE_TYPES)
        payables = self._get_open_items("liability_payable", PAYABLE_TYPES)

        def split(items):
            total = sum(item["amount"] for item in items)
            overdue = sum(item["amount"] for item in items if item["due"] < today)
            return total, overdue

        receivable_total, receivable_overdue = split(receivables)
        direct, channels, buckets = self._split_receivables(receivables)
        direct_total, direct_overdue = split(direct)
        # Pagáveis vivem no passivo: o residual é negativo. Invertemos para que a
        # tela mostre "quanto tenho a pagar" como número positivo.
        payable_total, payable_overdue = split(payables)
        payable_total, payable_overdue = -payable_total, -payable_overdue

        positions = self._get_cash_positions()
        cash = sum(position["statement_balance"] for position in positions)
        gaps = [
            position
            for position in positions
            if abs(position["gap"]) > RECONCILIATION_TOLERANCE
        ]

        companies = self.env.companies
        currencies = companies.mapped("currency_id")

        return {
            "today": today,
            "companies": companies.mapped("name"),
            "currency_id": companies[:1].currency_id.id,
            # Consolidar moedas diferentes exigiria conversão; hoje todas as
            # empresas são BRL. Se isso mudar, a tela avisa em vez de somar errado.
            "mixed_currencies": len(currencies) > 1,
            "cash": cash,
            "receivable_total": receivable_total,
            "receivable_overdue": receivable_overdue,
            "receivable_direct": direct_total,
            "receivable_direct_overdue": direct_overdue,
            "receivable_channels": [
                {
                    "code": channel["code"],
                    "label": channel["label"],
                    "in_flow": channel.get("in_flow", True),
                    "amount": sum(item["amount"] for item in buckets[channel["code"]]),
                    "count": len(buckets[channel["code"]]),
                }
                for channel in channels
                if buckets[channel["code"]]
            ],
            "payable_total": payable_total,
            "payable_overdue": payable_overdue,
            "net_position": cash + receivable_total - payable_total,
            "cash_positions": positions,
            "reconciliation_gaps": gaps,
            "unreconciled_entries": self._get_unreconciled_entries(),
            "settlement_health": self._get_settlement_health(),
        }

    @api.model
    def get_cash_flow(self, weeks=13):
        """Projeção semanal de caixa.

        O Odoo 19 não traz projeção de caixa — só o Cash Flow Statement, que olha
        para trás e fica atrás de grupo de contador. Aqui a linha do tempo é o
        saldo de hoje somado aos vencimentos futuros, semana a semana.
        """
        today = fields.Date.context_today(self)
        receivables = self._get_open_items("asset_receivable", RECEIVABLE_TYPES)
        payables = self._get_open_items("liability_payable", PAYABLE_TYPES)

        opening = sum(
            position["statement_balance"] for position in self._get_cash_positions()
        )

        # Cada canal entra com a data em que o dinheiro chega de verdade, e o
        # que já virou caixa (antecipado) sai da projeção — senão a mesma
        # entrada seria prometida duas vezes.
        direct, channels, by_channel = self._split_receivables(receivables)
        receivables = direct + [
            item
            for channel in channels
            if channel.get("in_flow", True)
            for item in by_channel[channel["code"]]
        ]
        already_advanced = sum(
            item["amount"]
            for channel in channels
            if not channel.get("in_flow", True)
            for item in by_channel[channel["code"]]
        )

        # Tudo que já venceu e não foi liquidado entra como um bucket próprio:
        # é caixa que deveria ter entrado ou saído e ainda está em aberto.
        overdue_in = sum(item["amount"] for item in receivables if item["due"] < today)
        overdue_out = -sum(item["amount"] for item in payables if item["due"] < today)

        weeks_buckets = []
        balance = opening
        for index in range(weeks):
            start = today + relativedelta(weeks=index)
            end = start + relativedelta(weeks=1)
            money_in = sum(
                item["amount"] for item in receivables if start <= item["due"] < end
            )
            money_out = -sum(
                item["amount"] for item in payables if start <= item["due"] < end
            )
            balance += money_in - money_out
            weeks_buckets.append(
                {
                    "start": start,
                    "end": end - relativedelta(days=1),
                    "in": money_in,
                    "out": money_out,
                    "net": money_in - money_out,
                    "balance": balance,
                }
            )

        return {
            "today": today,
            "opening": opening,
            "currency_id": self.env.companies[:1].currency_id.id,
            "overdue_in": overdue_in,
            "overdue_out": overdue_out,
            "already_advanced": already_advanced,
            "buckets": weeks_buckets,
            # A primeira semana em que o saldo projetado fica negativo é o que o
            # sócio precisa enxergar de imediato.
            "first_negative": next(
                (b["start"] for b in weeks_buckets if b["balance"] < 0), False
            ),
        }
