import { Component, onWillStart, useState } from "@odoo/owl";
import { deserializeDate, formatDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { formatMonetary } from "@web/views/fields/formatters";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

/**
 * Painel do Sócio: os números do financeiro consolidados das empresas ativas.
 *
 * Só lê. Quem precisa agir clica no cartão e cai na lista correspondente.
 */
export class FinanceOverview extends Component {
    static template = "itbr_finance_cockpit.Overview";
    static props = { ...standardActionServiceProps };
    static components = { ControlPanel };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, data: null });

        onWillStart(async () => {
            await this.load();
        });
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("itbr.finance.cockpit", "get_overview", []);
        this.state.loading = false;
    }

    money(value) {
        return formatMonetary(value || 0, { currencyId: this.state.data?.currency_id });
    }

    /** O backend serializa datas em ISO; a tela mostra no formato do usuário. */
    date(value) {
        return value ? formatDate(deserializeDate(value)) : "";
    }

    openReceivable() {
        this.action.doAction("itbr_finance_cockpit.action_finance_cockpit_receivable");
    }

    openPayable() {
        this.action.doAction("itbr_finance_cockpit.action_finance_cockpit_payable");
    }

    openCashFlow() {
        this.action.doAction("itbr_finance_cockpit.action_finance_cockpit_cash_flow");
    }

    /**
     * Sinais de que a posição da tela é de outra época.
     *
     * Fica acima dos cartões de propósito: quem lê o número precisa saber que
     * ele não reflete o banco antes de ler o número, não depois.
     */
    get health() {
        return this.state.data?.settlement_health;
    }

    /** Fatias do "a receber" que não vêm do cliente direto. */
    get channels() {
        return this.state.data?.receivable_channels || [];
    }

    /** Diários cujo saldo de extrato não bate com o saldo contábil. */
    get gaps() {
        return this.state.data?.reconciliation_gaps || [];
    }

    /** Lançamentos manuais parados em contas de cliente/fornecedor. */
    get strayEntries() {
        return this.state.data?.unreconciled_entries || [];
    }

    get companiesLabel() {
        const names = this.state.data?.companies || [];
        return names.length ? names.join(", ") : _t("nenhuma empresa ativa");
    }
}

registry.category("actions").add("itbr_finance_cockpit.Overview", FinanceOverview);
