# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Conta a receber padrão da empresa, e o que já foi postado na conta errada.

Isto é um assistente, e não um script, por um motivo prático: precisa rodar em
produção, na mão de quem administra o financeiro do cliente. O texto da tela é
parte da entrega — quem aperta o botão precisa entender o que muda antes de
apertar, e ver o antes/depois sem depender de quem escreveu o código.

Como o Odoo decide a conta a receber de uma fatura (account_move_line.py,
`_compute_account_id`): outra parcela do mesmo lançamento → propriedade do
parceiro → `ir.default` da empresa → primeira conta do tipo no plano. O degrau
que quase sempre decide é o `ir.default`, gravado quando o plano de contas foi
instalado — e é ele que este assistente lê e regrava.
"""

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import formatLang

# Só documento comercial é reclassificado. Lançamento manual parado em conta de
# cliente é problema de conciliação, não de configuração — o painel já o reporta
# à parte, e movê-lo em lote esconderia o que precisa ser olhado um a um.
RECEIVABLE_TYPES = ("out_invoice", "out_refund", "out_receipt")


class FinanceReceivableSetup(models.TransientModel):
    _name = "itbr.finance.receivable.setup"
    _description = "Conta a receber padrão"

    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
        domain=lambda self: [("id", "in", self.env.companies.ids)],
    )
    current_account_id = fields.Many2one(
        "account.account",
        string="Conta padrão hoje",
        compute="_compute_current_account_id",
        help="O que o Odoo usa hoje ao criar a parcela a receber de uma fatura.",
    )
    account_id = fields.Many2one(
        "account.account",
        string="Passar a usar",
        compute="_compute_account_id",
        store=True,
        readonly=False,
        # Sem required no campo: é computado e armazenado, então o Odoo insere a
        # linha antes de calcular, e a NOT NULL estouraria antes da sugestão
        # existir. A obrigatoriedade fica na view e em action_apply.
        check_company=True,
        domain="[('account_type', '=', 'asset_receivable'), ('company_ids', '=', company_id)]",
    )
    reclassify = fields.Boolean(
        string="Reclassificar o que já está em aberto",
        default=True,
        help="Move as parcelas a receber ainda não conciliadas para a conta escolhida. "
        "Não altera valor, data, parceiro nem nota fiscal — só a conta.",
    )
    batch_size = fields.Integer(
        string="Documentos por execução",
        default=500,
        help="Quantos documentos tratar de uma vez. O assistente informa quantos "
        "sobraram e continua de onde parou, para que a requisição nunca fique "
        "longa a ponto de o servidor derrubá-la. Zero trata todos de uma vez.",
    )
    preview_html = fields.Html(
        string="Simulação", compute="_compute_preview_html", sanitize=False
    )
    line_count = fields.Integer(compute="_compute_preview_html")
    move_count = fields.Integer(compute="_compute_preview_html")
    state = fields.Selection(
        [("draft", "Simulação"), ("done", "Aplicado")], default="draft"
    )
    result_html = fields.Html(string="Resultado", readonly=True, sanitize=False)
    remaining_moves = fields.Integer(readonly=True)
    can_continue = fields.Boolean(readonly=True)

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    @api.depends("company_id")
    def _compute_current_account_id(self):
        for wizard in self:
            account_id = self.env["ir.default"]._get(
                "res.partner",
                "property_account_receivable_id",
                company_id=wizard.company_id.id,
            )
            wizard.current_account_id = account_id or False

    @api.depends("company_id")
    def _compute_account_id(self):
        """Sugere a conta a receber do plano, sem escolher por conta própria.

        Aceitamos apenas a conta cujo nome é literalmente de clientes, e só
        quando é a única candidata. Com duas ou mais, o campo fica em branco de
        propósito: errar aqui manda todas as faturas seguintes para o lugar
        errado, e é exatamente esse o defeito que este assistente conserta.
        """
        for wizard in self:
            candidates = self.env["account.account"].search(
                [
                    *self.env["account.account"]._check_company_domain(wizard.company_id),
                    ("account_type", "=", "asset_receivable"),
                    ("name", "=ilike", "clientes"),
                ]
            )
            wizard.account_id = candidates if len(candidates) == 1 else False

    def _lines_to_reclassify(self):
        """Parcelas a receber de documento comercial fora da conta escolhida.

        Conciliada (inteira ou em parte) fica de fora: trocar a conta de uma
        linha com contrapartida desfaz a conciliação (account_move_line.write),
        e desfazer baixa de cliente em lote é dano, não conserto.
        """
        self.ensure_one()
        return self.env["account.move.line"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("display_type", "=", "payment_term"),
                ("account_id.account_type", "=", "asset_receivable"),
                ("account_id", "!=", self.account_id.id),
                ("parent_state", "=", "posted"),
                ("matching_number", "=", False),
                ("move_id.move_type", "in", RECEIVABLE_TYPES),
            ]
        )

    @api.depends("company_id", "account_id", "reclassify", "batch_size")
    def _compute_preview_html(self):
        for wizard in self:
            wizard.line_count = 0
            wizard.move_count = 0
            if not wizard.account_id or not wizard.reclassify:
                wizard.preview_html = False
                continue

            pending = wizard._lines_to_reclassify()
            wizard.move_count = len(pending.move_id)
            groups = self.env["account.move.line"]._read_group(
                [("id", "in", pending.ids)],
                groupby=["account_id"],
                aggregates=["balance:sum", "__count"],
            )
            if not groups:
                wizard.preview_html = Markup(
                    "<p class='text-muted'>Nada a reclassificar: todas as parcelas "
                    "a receber em aberto já estão na conta escolhida.</p>"
                )
                continue

            currency = wizard.company_id.currency_id
            rows = Markup("").join(
                Markup(
                    "<tr><td>%(name)s</td>"
                    "<td class='text-end'>%(count)s</td>"
                    "<td class='text-end'>%(total)s</td></tr>"
                )
                % {
                    "name": account.display_name,
                    "count": count,
                    "total": formatLang(self.env, total, currency_obj=currency),
                }
                for account, total, count in groups
            )
            wizard.line_count = sum(count for _account, _total, count in groups)
            table = Markup(
                "<table class='table table-sm'>"
                "<thead><tr><th>Sai de</th>"
                "<th class='text-end'>Parcelas</th>"
                "<th class='text-end'>Saldo</th></tr></thead>"
                "<tbody>%(rows)s</tbody></table>"
            ) % {"rows": rows}
            if wizard.batch_size and wizard.move_count > wizard.batch_size:
                table += Markup(
                    "<p class='text-muted small'>São %(moves)s documentos. Esta "
                    "execução trata os %(batch)s primeiros; ao final o assistente "
                    "diz quantos faltam e oferece continuar.</p>"
                ) % {"moves": wizard.move_count, "batch": wizard.batch_size}
            wizard.preview_html = table

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def action_apply(self):
        self.ensure_one()
        if not self.account_id:
            raise UserError(
                _(
                    "Escolha a conta a receber. Não foi possível sugerir uma: o plano "
                    "desta empresa não tem exatamente uma conta chamada 'Clientes'."
                )
            )
        if self.account_id.company_ids and self.company_id not in self.account_id.company_ids:
            raise UserError(_("A conta escolhida não pertence à empresa selecionada."))

        self.env["ir.default"].sudo().set(
            "res.partner",
            "property_account_receivable_id",
            self.account_id.id,
            company_id=self.company_id.id,
        )

        moved, blocked = (
            self._lines_to_reclassify()._itbr_move_to_account(
                self.account_id, limit=self.batch_size
            )
            if self.reclassify
            else (0, [])
        )

        self.state = "done"
        # Recontado depois de mover: é o que de fato sobrou, e é ele que decide
        # se ainda faz sentido oferecer "Continuar".
        self.remaining_moves = (
            len(self._lines_to_reclassify().move_id) if self.reclassify else 0
        )
        self.can_continue = bool(moved) and bool(self.remaining_moves)
        self.result_html = self._build_result_html(moved, blocked)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_continue(self):
        """Trata o próximo lote. O assistente sempre recalcula o que falta."""
        self.ensure_one()
        return self.action_apply()

    def _build_result_html(self, moved, blocked):
        self.ensure_one()
        parts = [
            Markup("<p>Conta a receber padrão de <b>%(company)s</b>: <b>%(account)s</b>.</p>")
            % {"company": self.company_id.name, "account": self.account_id.display_name},
        ]
        if self.reclassify:
            parts.append(
                Markup("<p>%(moved)s parcela(s) reclassificada(s).</p>") % {"moved": moved}
            )
        if self.remaining_moves:
            parts.append(
                Markup(
                    "<div class='alert alert-info'>Faltam <b>%(remaining)s</b> "
                    "documento(s). %(hint)s</div>"
                )
                % {
                    "remaining": self.remaining_moves,
                    "hint": (
                        "Use 'Continuar' para tratar o próximo lote."
                        if self.can_continue
                        else "Nenhum documento deste lote pôde ser alterado — veja abaixo."
                    ),
                }
            )
        if blocked:
            items = Markup("").join(
                Markup("<li><b>%(move)s</b>: %(error)s</li>")
                % {"move": move.display_name, "error": error}
                for move, error in blocked[:20]
            )
            parts.append(
                Markup(
                    "<div class='alert alert-warning'>"
                    "<b>%(count)s lançamento(s) não puderam ser alterados</b> — "
                    "normalmente data de bloqueio contábil. Ficaram na conta antiga:"
                    "<ul>%(items)s</ul></div>"
                )
                % {"count": len(blocked), "items": items}
            )
        return Markup("").join(parts)
