import { Component, onWillStart, useState } from "@odoo/owl";
import { deserializeDate, formatDate } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { formatMonetary } from "@web/views/fields/formatters";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

/**
 * Fluxo de caixa projetado.
 *
 * O Odoo 19 não tem projeção de caixa: o Cash Flow Statement olha para trás e
 * ainda exige grupo de contador. Aqui a linha do tempo parte do saldo de hoje e
 * soma os vencimentos futuros, semana a semana.
 */
export class FinanceCashFlow extends Component {
    static template = "itbr_finance_cockpit.CashFlow";
    static props = { ...standardActionServiceProps };
    static components = { ControlPanel };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, weeks: 13, data: null });

        onWillStart(async () => {
            await this.load();
        });
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("itbr.finance.cockpit", "get_cash_flow", [], {
            weeks: this.state.weeks,
        });
        this.state.loading = false;
    }

    async setHorizon(weeks) {
        this.state.weeks = weeks;
        await this.load();
    }

    money(value) {
        return formatMonetary(value || 0, { currencyId: this.state.data?.currency_id });
    }

    /** O backend serializa datas em ISO; a tela mostra no formato do usuário. */
    date(value) {
        return value ? formatDate(deserializeDate(value)) : "";
    }

    /** Largura relativa da barra, para dar noção visual sem depender de gráfico. */
    barWidth(value) {
        const buckets = this.state.data?.buckets || [];
        const peak = Math.max(
            1,
            ...buckets.map((b) => Math.max(Math.abs(b.in), Math.abs(b.out)))
        );
        return `${Math.min(100, (Math.abs(value) / peak) * 100)}%`;
    }

    get hasOverdue() {
        const data = this.state.data;
        return Boolean(data && (data.overdue_in || data.overdue_out));
    }
}

registry.category("actions").add("itbr_finance_cockpit.CashFlow", FinanceCashFlow);
