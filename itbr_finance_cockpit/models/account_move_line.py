# Copyright 2026 IT Brasil
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Reclassificação em lote de parcelas já postadas."""

from collections import defaultdict

from odoo import models
from odoo.exceptions import UserError

# Documentos por savepoint. Ver _itbr_move_to_account.
CHUNK_SIZE = 200


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _itbr_move_to_account(self, account, limit=0):
        """Move estas parcelas para outra conta, em blocos.

        Trocar a conta de uma parcela postada é permitido pelo Odoo (ver
        `write` em account.move.line, que inclusive prevê mudar a conta de uma
        conciliação inteira). O que atrapalha é tempo: um savepoint por
        documento custava cinco minutos e meio nos ~1.500 documentos desta
        base — tempo de sobra para o watchdog do worker derrubar a requisição
        em produção, onde o limite é menor que o daqui.

        Então vai em bloco: no caminho feliz é uma escrita só, e apenas o bloco
        que cai (data de bloqueio contábil, trava do localizador) é refeito
        documento a documento, para que um travado não leve junto os outros.

        :param limit: máximo de documentos a tratar; 0 trata todos.
        :return: (parcelas movidas, [(lançamento, erro)])
        """
        lines_by_move = defaultdict(lambda: self.env["account.move.line"])
        for line in self:
            lines_by_move[line.move_id] += line

        moves = list(lines_by_move)
        if limit:
            moves = moves[:limit]

        moved = 0
        blocked = []
        for start in range(0, len(moves), CHUNK_SIZE):
            chunk = moves[start : start + CHUNK_SIZE]
            chunk_lines = self.browse().union(*(lines_by_move[move] for move in chunk))
            try:
                with self.env.cr.savepoint():
                    chunk_lines.account_id = account
            except UserError:
                for move in chunk:
                    try:
                        with self.env.cr.savepoint():
                            lines_by_move[move].account_id = account
                    except UserError as error:
                        blocked.append((move, str(error)))
                    else:
                        moved += len(lines_by_move[move])
            else:
                moved += len(chunk_lines)
        return moved, blocked
