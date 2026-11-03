Duas regras de vencimento que o prazo de pagamento padrão do Odoo não tem:

- **Dia da semana do mês**: a N-ésima ocorrência de um dia da semana, X meses depois do mês
  da fatura. Ex.: "1ª quinta-feira, 2 meses depois" vence uma fatura de 01/10 em 03/12.
- **Só dia útil**: o vencimento nunca cai em fim de semana ou feriado do calendário de
  trabalho da empresa. No dia da semana do mês, conta só as ocorrências úteis; nos demais
  tipos, passa para o próximo dia útil (dia 20 num domingo vira dia 21).

Os feriados são as folgas gerais (sem recurso) do calendário de trabalho da empresa.
