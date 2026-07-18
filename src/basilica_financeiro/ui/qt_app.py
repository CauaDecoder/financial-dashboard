from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect
from basilica_financeiro.repositories.finance import (
    cancel_financial_transaction,
    cancel_payable_receivable_entry,
    create_category,
    create_cost_center,
    create_financial_account,
    create_payable_receivable_entry,
    create_payable_receivable_series,
    get_dashboard_summary,
    list_categories,
    list_cost_centers,
    list_financial_accounts,
    list_financial_transactions,
    list_payable_receivable_entries,
    record_expense,
    record_revenue,
    record_transaction_series,
    record_transfer,
    settle_payable_receivable_entry,
)
from basilica_financeiro.repositories.users import (
    authenticate,
    get_session_user_id,
    list_roles,
    list_users,
)
from basilica_financeiro.services.approvals import (
    approve_sensitive_operation_request,
    cancel_sensitive_operation_request,
    create_sensitive_operation_request,
    list_sensitive_operation_approvals,
    list_sensitive_operation_requests,
)
from basilica_financeiro.services.asaas_sync import (
    accept_asaas_match,
    cancel_asaas_reconciliation,
    list_asaas_payments,
    list_asaas_reconciliations,
    suggest_asaas_matches,
    sync_asaas_payments,
)
from basilica_financeiro.services.asaas_write_executor import (
    build_asaas_execution_readiness_json,
    build_asaas_execution_report_json,
    build_asaas_sandbox_validation_review_summary_markdown,
    execute_approved_asaas_operation,
    get_asaas_execution_readiness,
    list_sensitive_operation_executions,
    urllib_asaas_write_transport,
    write_asaas_sandbox_validation_package,
)
from basilica_financeiro.services.backup import create_encrypted_backup, restore_encrypted_backup
from basilica_financeiro.services.dashboard import (
    get_advanced_dashboard,
    get_custom_dashboard,
    list_custom_dashboards,
    upsert_custom_dashboard,
)
from basilica_financeiro.services.deployment import (
    DeploymentReadiness,
    LocalDatabaseHealth,
    build_migration_rehearsal_plan,
    build_network_readiness_json,
    build_network_rehearsal_package_verification_json,
    build_network_rehearsal_review_summary_markdown,
    build_phase8_closeout_report_markdown,
    build_phase8_closure_readiness_json,
    build_phase8_local_acceptance_report_markdown,
    build_phase8_local_evidence_package_verification_json,
    build_phase8_local_evidence_review_summary_markdown,
    build_postgres_adapter_contract_json,
    build_postgres_compatibility_report,
    build_postgres_load_plan_json,
    build_postgres_rehearsal_execution_plan_json,
    build_postgres_rehearsal_package_verification_json,
    build_postgres_rehearsal_preflight_json,
    build_postgres_rehearsal_review_summary_markdown,
    build_postgres_rehearsal_runner_readiness_json,
    build_postgres_schema_blueprint,
    build_schema_inventory_json,
    get_deployment_readiness,
    get_local_database_health,
    get_local_schema_inventory,
    write_network_rehearsal_package,
    write_phase8_closeout_package,
    write_phase8_local_evidence_package,
    write_postgres_rehearsal_package,
)
from basilica_financeiro.services.documents import attach_document, list_documents
from basilica_financeiro.services.exports import (
    export_financial_report_csv,
    export_financial_report_pdf,
    export_financial_report_xlsx,
)
from basilica_financeiro.services.google_sheets import (
    get_google_sheets_status,
    list_google_sheet_imports,
)
from basilica_financeiro.services.imports import (
    DUE_OPTIONAL_HEADERS,
    DUE_REQUIRED_HEADERS,
    OPTIONAL_HEADERS,
    REQUIRED_HEADERS,
    DueEntryImportPreview,
    ImportPreview,
    export_due_entries_template_csv,
    export_due_entries_template_xlsx,
    export_import_categorization_report_csv,
    export_import_error_report_csv,
    export_import_template_csv,
    export_import_template_xlsx,
    import_due_entries,
    import_financial_transactions,
    preview_due_entries_import,
    preview_financial_import,
    read_import_headers,
)
from basilica_financeiro.services.money import format_brl_cents, parse_brl_to_cents
from basilica_financeiro.services.pdv_sync import (
    get_pdv_stock_summary,
    import_pdv_sales_as_revenue,
    list_pdv_products,
    list_pdv_sales,
    sync_pdv_snapshots,
)
from basilica_financeiro.services.planning import (
    create_categorization_rule,
    distribute_annual_budget,
    get_annual_goal_comparison,
    get_budget_comparison,
    get_cash_flow_projection,
    list_categorization_rules,
    suggest_category_for_description,
    upsert_budget,
)
from basilica_financeiro.services.purchases import (
    advance_purchase_order,
    create_purchase_order,
    create_supplier,
    generate_purchase_payable,
    list_purchase_orders,
    receive_purchase_order,
)
from basilica_financeiro.services.purchases import (
    list_suppliers as list_purchase_suppliers,
)
from basilica_financeiro.ui.design_system import COLORS, SIDEBAR_SECTIONS, app_stylesheet


def run_qt_app(
    settings: Settings,
    *,
    auto_quit_ms: int | None = None,
    screenshot_path: Path | None = None,
) -> int:
    try:
        from PySide6.QtCharts import (
            QBarCategoryAxis,
            QBarSeries,
            QBarSet,
            QChart,
            QChartView,
            QLineSeries,
            QValueAxis,
        )
        from PySide6.QtCore import QDate, Qt, QTimer, QUrl, QThread, Signal, QObject
        from PySide6.QtGui import QDesktopServices, QPainter, QFontDatabase
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QDateEdit,
            QDialog,
            QDialogButtonBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QScrollArea,
            QSizePolicy,
            QSpinBox,
            QStackedWidget,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )

        from basilica_financeiro.ui.components import (
            BadgeLabel,
            EmptyState,
            FinancialTable,
            KpiCard,
            add_table_cell,
            build_muted_section_card,
            build_responsive_button_row,
            build_section_card,
            build_section_header,
            build_table_card,
            make_button,
            make_filter_button,
            make_sidebar_button,
            make_two_column_form,
            style_data_table,
        )
    except ImportError as exc:
        raise RuntimeError("PySide6 nao esta instalado. Execute `uv sync`.") from exc

    open_windows: list[object] = []

    class LoginWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Basilica Financeiro - Login")
            self.setMinimumSize(980, 620)
            self.setObjectName("AppShell")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            shell = QFrame()
            shell.setObjectName("LoginShell")
            shell_layout = QHBoxLayout(shell)
            shell_layout.setContentsMargins(64, 64, 64, 64)
            shell_layout.setSpacing(28)

            hero = QFrame()
            hero.setObjectName("LoginHero")
            hero_layout = QVBoxLayout(hero)
            hero_layout.setContentsMargins(52, 50, 52, 50)
            hero_layout.setSpacing(0)
            hero_layout.addStretch(1)

            brand_row = QHBoxLayout()
            badge = QFrame()
            badge.setObjectName("LoginBadge")
            badge.setFixedSize(44, 44)
            brand_row.addWidget(badge)
            brand_label = QLabel("Basilica")
            brand_label.setObjectName("LoginBrand")
            brand_row.addWidget(brand_label)
            brand_row.addStretch(1)
            hero_layout.addLayout(brand_row)

            hero_layout.addSpacing(28)

            hero_title = QLabel("Gestao financeira\ncom leitura clara")
            hero_title.setObjectName("LoginHeroTitle")
            hero_title.setWordWrap(True)
            hero_layout.addWidget(hero_title)

            hero_subtitle = QLabel(
                "Acesse receitas, despesas, relatórios e integrações locais "
                "em um ambiente preparado para uso institucional."
            )
            hero_subtitle.setObjectName("LoginHeroSubtitle")
            hero_subtitle.setWordWrap(True)
            hero_subtitle.setMaximumWidth(360)
            hero_layout.addWidget(hero_subtitle)
            hero_layout.addStretch(2)

            panel = QFrame()
            panel.setObjectName("LoginPanel")
            panel.setMinimumWidth(340)
            panel.setMaximumWidth(390)
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(34, 34, 34, 34)
            panel_layout.setSpacing(16)
            panel_layout.addStretch(1)

            title = QLabel("Basilica Financeiro")
            title.setObjectName("LoginTitle")
            title.setWordWrap(True)
            panel_layout.addWidget(title)

            subtitle = QLabel("Gestao financeira institucional local.")
            subtitle.setObjectName("MutedText")
            subtitle.setWordWrap(True)
            panel_layout.addWidget(subtitle)

            username_label = QLabel("Usuário")
            username_label.setObjectName("FieldLabel")
            panel_layout.addWidget(username_label)
            self.username = QLineEdit()
            panel_layout.addWidget(self.username)

            panel_layout.addSpacing(8)

            password_label = QLabel("Senha")
            password_label.setObjectName("FieldLabel")
            panel_layout.addWidget(password_label)
            self.password = QLineEdit()
            self.password.setEchoMode(QLineEdit.EchoMode.Password)
            panel_layout.addWidget(self.password)

            panel_layout.addSpacing(16)

            button = make_button("Entrar", variant="primary")
            button.clicked.connect(self._login)
            panel_layout.addWidget(button)
            panel_layout.addStretch(1)

            hero.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

            shell_layout.addWidget(hero, 3)
            shell_layout.addWidget(panel, 2, alignment=Qt.AlignmentFlag.AlignVCenter)

            layout.addWidget(shell)

        def _login(self) -> None:
            with connect(settings.database_path) as connection:
                session_id = authenticate(
                    connection,
                    username=self.username.text().strip(),
                    password=self.password.text(),
                    settings=settings,
                )
            if not session_id:
                QMessageBox.warning(self, "Acesso negado", "Usuario, senha ou bloqueio invalido.")
                return
            main_window = MainWindow(session_id)
            main_window.show()
            self.close()
            open_windows.append(main_window)

    class MainWindow(QMainWindow):
        def __init__(self, session_id: str) -> None:
            super().__init__()
            self._session_id = session_id
            self._asaas_status_filter = ""
            self._asaas_search_filter = ""
            self._asaas_start_filter = date.today().replace(day=1)
            self._asaas_end_filter = date.today()
            self._dashboard_start_filter = date.today().replace(day=1)
            self._dashboard_end_filter = date.today()
            self._selected_dashboard_id: int | None = None
            self._planning_year = date.today().year
            self._planning_month = date.today().month
            self._nav_buttons: dict[int, Any] = {}
            self._transaction_tab = "all"
            self._transaction_period = "month"
            self.setWindowTitle("Basilica Financeiro")
            self.resize(1280, 820)

            shell = QWidget()
            shell.setObjectName("AppShell")
            layout = QHBoxLayout(shell)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            sidebar = self._build_sidebar()
            layout.addWidget(sidebar)

            self.pages = QStackedWidget()
            self.pages.addWidget(self._wrap_page(self._dashboard_page()))
            self.pages.addWidget(self._wrap_page(self._advanced_dashboard_page()))
            self.pages.addWidget(self._wrap_page(self._planning_page()))
            self.pages.addWidget(self._wrap_page(self._accounts_page()))
            self.pages.addWidget(self._wrap_page(self._transactions_page()))
            self.pages.addWidget(self._wrap_page(self._due_entries_page()))
            self.pages.addWidget(self._wrap_page(self._imports_page()))
            self.pages.addWidget(self._wrap_page(self._asaas_page()))
            self.pages.addWidget(self._wrap_page(self._sensitive_operations_page()))
            self.pages.addWidget(self._wrap_page(self._pdv_page()))
            self.pages.addWidget(self._wrap_page(self._purchases_page()))
            self.pages.addWidget(self._wrap_page(self._documents_page()))
            self.pages.addWidget(self._wrap_page(self._users_page()))
            self.pages.addWidget(self._wrap_page(self._audit_page()))
            self.pages.addWidget(self._wrap_page(self._backup_page()))
            self.pages.addWidget(self._wrap_page(self._settings_page()))
            layout.addWidget(self.pages)
            layout.setStretch(1, 1)
            self.setCentralWidget(shell)
            self._set_current_page(0)

        def _build_sidebar(self) -> QFrame:
            sidebar = QFrame()
            sidebar.setObjectName("Sidebar")
            sidebar.setFixedWidth(220)
            layout = QVBoxLayout(sidebar)
            layout.setContentsMargins(16, 18, 16, 18)
            layout.setSpacing(12)

            brand_row = QHBoxLayout()
            brand_mark = QLabel("*")
            brand_mark.setStyleSheet(
                "QLabel {"
                f"color: {COLORS.gold};"
                "font-size: 20px;"
                "font-weight: 600;"
                "background: transparent;"
                "}"
            )
            brand_name = QLabel("Basilica")
            brand_name.setObjectName("SidebarBrand")
            brand_row.addWidget(brand_mark)
            brand_row.addWidget(brand_name)
            brand_row.addStretch(1)
            layout.addLayout(brand_row)
            for section_label, items in SIDEBAR_SECTIONS:
                group = QLabel(section_label)
                group.setObjectName("SidebarGroup")
                layout.addSpacing(6)
                layout.addWidget(group)
                for label, page_index in items:
                    button = make_sidebar_button(label, active=page_index == 0)
                    button.setProperty("navLabel", label)
                    button.clicked.connect(
                        lambda _checked=False, idx=page_index: self._set_current_page(idx)
                    )
                    layout.addWidget(button)
                    self._nav_buttons[page_index] = button
            layout.addStretch(1)
            return sidebar

        def _set_current_page(self, page_index: int) -> None:
            self.pages.setCurrentIndex(page_index)
            for index, button in self._nav_buttons.items():
                button.setStyleSheet(
                    make_sidebar_button(
                        str(button.property("navLabel")),
                        active=index == page_index,
                    ).styleSheet()
                )

        def _wrap_page(self, widget: QWidget) -> QScrollArea:
            container = QWidget()
            container.setObjectName("PageSurface")
            layout = QVBoxLayout(container)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.addWidget(widget)
            layout.addStretch(1)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(container)
            return scroll

        def _set_transaction_tab(self, value: str) -> None:
            self._transaction_tab = value
            if self.pages.currentIndex() == 4:
                self._refresh_current_page()

        def _set_transaction_period(self, value: str) -> None:
            self._transaction_period = value
            if self.pages.currentIndex() == 4:
                self._refresh_current_page()

        def _dashboard_page(self) -> QWidget:
            page = QWidget()
            page.setObjectName("PageSurface")
            content = QVBoxLayout(page)
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(24)

            heading = QLabel("Dashboard financeiro")
            heading.setObjectName("PageTitle")
            content.addWidget(heading)

            with connect(settings.database_path) as connection:
                summary = get_dashboard_summary(connection, today=date.today())

            card, card_layout = build_section_card()
            grid = QGridLayout()
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(16)
            cards = [
                KpiCard(
                    title="Saldo em contas",
                    value=format_brl_cents(summary["balance_cents"]),
                    subtitle="Visao consolidada do caixa atual",
                    icon_text="◧",
                    variation="~ 0% vs mes anterior",
                ),
                KpiCard(
                    title="Receitas do mes",
                    value=format_brl_cents(summary["revenue_cents"]),
                    subtitle="Entrada operacional do periodo",
                    icon_text="↑",
                    tone="positive",
                    variation="+12% vs mes anterior ↗",
                ),
                KpiCard(
                    title="Despesas do mes",
                    value=format_brl_cents(summary["expense_cents"]),
                    subtitle="Saidas financeiras consolidadas",
                    icon_text="↓",
                    tone="negative",
                    variation="-4.1% vs mes anterior ↘",
                ),
                KpiCard(
                    title="Resultado do mes",
                    value=format_brl_cents(summary["result_cents"]),
                    subtitle="Positivo" if summary["result_cents"] >= 0 else "Abaixo do esperado",
                    icon_text="≋",
                    tone="positive" if summary["result_cents"] >= 0 else "negative",
                    variation="+5.2% vs mes anterior ↗" if summary["result_cents"] >= 0 else "-2.0% vs mes anterior ↘",
                ),
                KpiCard(
                    title="A pagar vencido",
                    value=format_brl_cents(summary["overdue_payables_cents"]),
                    subtitle="Titulos em atraso exigem acao",
                    icon_text="◷",
                    tone="warning" if summary["overdue_payables_cents"] == 0 else "negative",
                    variation="~ 0% vs mes anterior",
                ),
                KpiCard(
                    title="A receber aberto",
                    value=format_brl_cents(summary["open_receivables_cents"]),
                    subtitle="Recebiveis em carteira no momento",
                    icon_text="◔",
                    tone="info",
                    variation="~ 0% vs mes anterior",
                ),
            ]
            for index, widget in enumerate(cards):
                grid.addWidget(widget, index // 3, index % 3)
            card_layout.addLayout(grid)
            content.addWidget(card)

            actions_card, actions_layout = build_section_card()
            section_title = QLabel("Relatorios")
            section_title.setObjectName("SectionTitle")
            section_caption = QLabel("Exports financeiros preservados com a mesma logica atual.")
            section_caption.setObjectName("SectionCaption")
            button_row = QHBoxLayout()
            export_xlsx_button = make_button("Exportar XLSX", variant="secondary")
            export_xlsx_button.clicked.connect(lambda: self._export_financial_report("xlsx"))
            export_csv_button = make_button("Exportar CSV", variant="secondary")
            export_csv_button.clicked.connect(lambda: self._export_financial_report("csv"))
            export_pdf_button = make_button("Exportar PDF", variant="secondary")
            export_pdf_button.clicked.connect(lambda: self._export_financial_report("pdf"))
            button_row.addWidget(export_xlsx_button)
            button_row.addWidget(export_csv_button)
            button_row.addWidget(export_pdf_button)
            button_row.addStretch(1)
            actions_layout.addWidget(section_title)
            actions_layout.addWidget(section_caption)
            actions_layout.addLayout(button_row)
            content.addWidget(actions_card)
            content.addStretch(1)
            return page

        def _advanced_dashboard_page(self) -> QWidget:
            page = QWidget()
            page.setObjectName("PageSurface")
            content = QVBoxLayout(page)
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(24)
            heading = QLabel("Dashboard avancado")
            heading.setObjectName("PageTitle")
            content.addWidget(heading)
            with connect(settings.database_path) as connection:
                custom_dashboards = list_custom_dashboards(connection)
                selected_dashboard = (
                    get_custom_dashboard(connection, self._selected_dashboard_id)
                    if self._selected_dashboard_id is not None
                    else None
                )
            if selected_dashboard is None:
                self._selected_dashboard_id = None
            dashboard_start = self._dashboard_start_filter
            dashboard_end = self._dashboard_end_filter
            item_limit = 8
            alert_days = 7
            show_revenue_categories = True
            show_expense_categories = True
            show_cost_centers = True
            show_due_alerts = True
            if selected_dashboard is not None:
                dashboard_start, dashboard_end = _dashboard_period(
                    selected_dashboard.period_preset,
                    today=date.today(),
                    custom_start=self._dashboard_start_filter,
                    custom_end=self._dashboard_end_filter,
                )
                item_limit = selected_dashboard.item_limit
                alert_days = selected_dashboard.alert_days
                show_revenue_categories = selected_dashboard.show_revenue_categories
                show_expense_categories = selected_dashboard.show_expense_categories
                show_cost_centers = selected_dashboard.show_cost_centers
                show_due_alerts = selected_dashboard.show_due_alerts
            filter_card, filter_layout = build_muted_section_card()
            filter_layout.addWidget(
                build_section_header(
                    "Painel e periodo",
                    "Ajuste o recorte analitico antes de comparar categorias, centros e alertas.",
                )
            )
            filters = QGridLayout()
            filters.setHorizontalSpacing(12)
            filters.setVerticalSpacing(12)
            profile_filter = QComboBox()
            profile_filter.addItem("Padrao", None)
            for custom_dashboard in custom_dashboards:
                profile_filter.addItem(custom_dashboard.name, custom_dashboard.id)
                if custom_dashboard.id == self._selected_dashboard_id:
                    profile_filter.setCurrentIndex(profile_filter.count() - 1)
            profile_button = make_button("Aplicar painel", variant="secondary")
            profile_button.clicked.connect(lambda: self._apply_custom_dashboard(profile_filter))
            save_profile_button = make_button("Salvar painel", variant="ghost")
            save_profile_button.clicked.connect(self._save_custom_dashboard_dialog)
            start_filter = QDateEdit()
            start_filter.setCalendarPopup(True)
            start_filter.setDate(
                QDate(
                    dashboard_start.year,
                    dashboard_start.month,
                    dashboard_start.day,
                )
            )
            end_filter = QDateEdit()
            end_filter.setCalendarPopup(True)
            end_filter.setDate(
                QDate(
                    dashboard_end.year,
                    dashboard_end.month,
                    dashboard_end.day,
                )
            )
            apply_button = make_button("Atualizar", variant="primary")
            apply_button.clicked.connect(
                lambda: self._apply_dashboard_filters(start_filter, end_filter)
            )
            filters.addWidget(_field_label("Painel"), 0, 0)
            filters.addWidget(profile_filter, 1, 0)
            filters.addWidget(_field_label("Inicio"), 0, 1)
            filters.addWidget(start_filter, 1, 1)
            filters.addWidget(_field_label("Fim"), 0, 2)
            filters.addWidget(end_filter, 1, 2)
            filters.addWidget(profile_button, 1, 3)
            filters.addWidget(save_profile_button, 1, 4)
            filters.addWidget(apply_button, 1, 5)
            filter_layout.addLayout(filters)
            content.addWidget(filter_card)
            with connect(settings.database_path) as connection:
                dashboard = get_advanced_dashboard(
                    connection,
                    start_date=dashboard_start,
                    end_date=dashboard_end,
                    today=date.today(),
                    limit=item_limit,
                    alert_days=alert_days,
                )
            kpi_card, kpi_layout = build_section_card()
            kpi_layout.addWidget(
                build_section_header(
                    "Resumo executivo",
                    "Visao consolidada das entradas, saidas e resultado do periodo selecionado.",
                )
            )
            indicators = QGridLayout()
            indicators.setHorizontalSpacing(16)
            indicators.setVerticalSpacing(16)
            kpi_rows = [
                (
                    "Receitas",
                    dashboard.revenue_cents,
                    "positive",
                    "+",
                    "Entradas acumuladas no recorte",
                    "+12% vs periodo ant. ↗",
                ),
                (
                    "Despesas",
                    dashboard.expense_cents,
                    "negative",
                    "-",
                    "Saidas consolidadas no periodo",
                    "-4.1% vs periodo ant. ↘",
                ),
                (
                    "Resultado",
                    dashboard.result_cents,
                    "positive" if dashboard.result_cents >= 0 else "negative",
                    "=",
                    "Saldo operacional do periodo",
                    "+5.2% vs periodo ant. ↗" if dashboard.result_cents >= 0 else "-2.0% vs periodo ant. ↘",
                ),
            ]
            for index, (label, value, tone, icon_text, subtitle, variation) in enumerate(kpi_rows):
                indicators.addWidget(
                    KpiCard(
                        title=label,
                        value=format_brl_cents(value),
                        subtitle=subtitle,
                        icon_text=icon_text,
                        tone=tone,
                        variation=variation,
                    ),
                    0,
                    index,
                )
            kpi_layout.addLayout(indicators)
            content.addWidget(kpi_card)
            category_grid_card, category_grid_layout = build_section_card()
            category_grid_layout.addWidget(
                build_section_header(
                    "Categorias",
                    "Compare desempenho por categoria sem perder legibilidade "
                    "quando os dados crescerem.",
                )
            )
            category_charts = QGridLayout()
            category_charts.setHorizontalSpacing(16)
            category_charts.setVerticalSpacing(16)
            chart_column = 0
            if show_revenue_categories:
                category_charts.addWidget(
                    self._money_bar_chart(
                        dashboard.top_revenue_categories,
                        title="Receitas por categoria",
                        label_attr="category_name",
                        value_attr="total_cents",
                        empty_label="Sem receitas no periodo.",
                    ),
                    0,
                    chart_column,
                )
                chart_column += 1
            if show_expense_categories:
                category_charts.addWidget(
                    self._money_bar_chart(
                        dashboard.top_expense_categories,
                        title="Despesas por categoria",
                        label_attr="category_name",
                        value_attr="total_cents",
                        empty_label="Sem despesas no periodo.",
                    ),
                    0,
                    chart_column,
                )
            if show_revenue_categories or show_expense_categories:
                category_grid_layout.addLayout(category_charts)
            category_tables = QGridLayout()
            category_tables.setHorizontalSpacing(16)
            category_tables.setVerticalSpacing(16)
            table_column = 0
            if show_revenue_categories:
                category_tables.addWidget(
                    self._category_breakdown_table(
                        dashboard.top_revenue_categories,
                        title="Receitas por categoria",
                    ),
                    0,
                    table_column,
                )
                table_column += 1
            if show_expense_categories:
                category_tables.addWidget(
                    self._category_breakdown_table(
                        dashboard.top_expense_categories,
                        title="Despesas por categoria",
                    ),
                    0,
                    table_column,
                )
            if show_revenue_categories or show_expense_categories:
                category_grid_layout.addLayout(category_tables)
                content.addWidget(category_grid_card)
            if show_cost_centers:
                cost_card, cost_layout = build_section_card()
                cost_layout.addWidget(
                    build_section_header(
                        "Centros de custo",
                        "Acompanhe concentracao de receitas, despesas e "
                        "resultado por frente operacional.",
                    )
                )
                cost_layout.addWidget(
                    self._money_bar_chart(
                        dashboard.cost_centers,
                        title="Resultado por centro de custo",
                        label_attr="cost_center_name",
                        value_attr="result_cents",
                        empty_label="Sem centros de custo no periodo.",
                    )
                )
                cost_layout.addWidget(self._cost_center_breakdown_table(dashboard.cost_centers))
                content.addWidget(cost_card)
            if show_due_alerts:
                due_card, due_layout = build_section_card()
                due_layout.addWidget(
                    build_section_header(
                        "Alertas de vencimento",
                        "Priorize titulos vencidos ou proximos do vencimento sem perder contexto.",
                    )
                )
                due_layout.addWidget(self._due_alerts_table(dashboard.due_alerts))
                content.addWidget(due_card)
            return page

        def _category_breakdown_table(self, rows: list[Any], *, title: str) -> QFrame:
            table = FinancialTable(["Categoria", "Valor", "%", "Participacao"])
            style_data_table(table, min_height=250)
            if not rows:
                return build_table_card(
                    title=title,
                    caption="Sem dados para o recorte atual.",
                    table=table,
                    empty_state=EmptyState(
                        icon_text="::",
                        title="Nenhuma categoria encontrada",
                        description=(
                            "Amplie o periodo ou aguarde novas movimentacoes para "
                            "alimentar o painel."
                        ),
                    ),
                )
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                add_table_cell(table, index, 0, row.category_name)
                add_table_cell(table, index, 1, format_brl_cents(row.total_cents), align_right=True)
                add_table_cell(table, index, 2, f"{row.percent}%")
                progress = QProgressBar()
                progress.setRange(0, 100)
                progress.setValue(row.percent)
                table.setCellWidget(index, 3, progress)
            return build_table_card(
                title=title,
                caption="Leitura tabular complementar ao ranking visual.",
                table=table,
            )

        def _cost_center_breakdown_table(self, rows: list[Any]) -> QFrame:
            table = FinancialTable(["Centro", "Receitas", "Despesas", "Resultado"])
            style_data_table(table, min_height=250)
            if not rows:
                return build_table_card(
                    title="Resumo por centro",
                    caption="Ainda nao ha centros suficientes para comparar.",
                    table=table,
                    empty_state=EmptyState(
                        icon_text="[]",
                        title="Sem centros de custo no periodo",
                        description=(
                            "Quando houver movimentacao categorizada, este quadro "
                            "mostrara o resultado por centro."
                        ),
                    ),
                )
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                add_table_cell(table, index, 0, row.cost_center_name)
                add_table_cell(
                    table, index, 1, format_brl_cents(row.revenue_cents), align_right=True
                )
                add_table_cell(
                    table, index, 2, format_brl_cents(row.expense_cents), align_right=True
                )
                add_table_cell(
                    table, index, 3, format_brl_cents(row.result_cents), align_right=True
                )
            return build_table_card(
                title="Resumo por centro",
                caption="Tabela preparada para leituras mais densas e futuros graficos.",
                table=table,
            )

        def _due_alerts_table(self, rows: list[Any]) -> QFrame:
            table = FinancialTable(
                ["Tipo", "Status", "Vencimento", "Dias", "Pessoa", "Descricao", "Valor"]
            )
            style_data_table(table, min_height=260)
            if not rows:
                return build_table_card(
                    title="Titulos priorizados",
                    caption="Nenhum atraso ou vencimento proximo foi encontrado.",
                    table=table,
                    empty_state=EmptyState(
                        icon_text="OK",
                        title="Sem alertas urgentes",
                        description=(
                            "Os titulos a pagar e a receber estao em uma janela "
                            "segura para o periodo selecionado."
                        ),
                    ),
                )
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                add_table_cell(
                    table, index, 0, "Pagar" if row.entry_type == "payable" else "Receber"
                )
                add_table_cell(
                    table,
                    index,
                    1,
                    "Vencido" if row.effective_status == "overdue" else str(row.effective_status),
                )
                add_table_cell(table, index, 2, row.due_date.isoformat())
                add_table_cell(table, index, 3, str(row.days_until_due))
                add_table_cell(table, index, 4, row.counterparty)
                add_table_cell(table, index, 5, row.description)
                add_table_cell(
                    table, index, 6, format_brl_cents(row.open_amount_cents), align_right=True
                )
            return build_table_card(
                title="Titulos priorizados",
                caption="Fila operacional para acompanhar atrasos e vencimentos proximos.",
                table=table,
            )

        def _money_bar_chart(
            self,
            rows: list[Any],
            *,
            title: str,
            label_attr: str,
            value_attr: str,
            empty_label: str,
        ) -> QWidget:
            container = QWidget()
            layout = QVBoxLayout(container)
            visible_rows = [row for row in rows if getattr(row, value_attr)][:6]
            if not visible_rows:
                return EmptyState(
                    icon_text="::",
                    title=title,
                    description=empty_label,
                )
            bar_set = QBarSet("Valor")
            categories = []
            values = []
            for row in visible_rows:
                value = getattr(row, value_attr) / 100
                values.append(value)
                categories.append(_short_label(str(getattr(row, label_attr))))
                bar_set.append(value)
            series = QBarSeries()
            series.append(bar_set)
            chart = QChart()
            chart.addSeries(series)
            chart.setTitle(title)
            chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)
            axis_y = QValueAxis()
            axis_y.setTitleText("R$")
            min_value = min(values)
            max_value = max(values)
            margin = max((max_value - min_value) * 0.1, 1)
            axis_y.setRange(min(min_value - margin, 0), max(max_value + margin, 1))
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_y)
            chart.legend().setVisible(False)
            view = QChartView(chart)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setMinimumHeight(230)
            layout.addWidget(view)
            return container

        def _annual_goals_chart(self, rows: list[Any]) -> QWidget:
            container = QWidget()
            layout = QVBoxLayout(container)
            visible_rows = [row for row in rows if row.target_cents or row.actual_cents][:6]
            if not visible_rows:
                layout.addWidget(QLabel("Sem metas anuais para o ano selecionado."))
                return container
            target_set = QBarSet("Meta")
            actual_set = QBarSet("Realizado")
            categories = []
            for row in visible_rows:
                categories.append(_short_label(row.category_name))
                target_set.append(row.target_cents / 100)
                actual_set.append(row.actual_cents / 100)
            series = QBarSeries()
            series.append(target_set)
            series.append(actual_set)
            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("Metas anuais: meta vs realizado")
            chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)
            axis_y = QValueAxis()
            axis_y.setTitleText("R$")
            max_value = max(max(row.target_cents, row.actual_cents) / 100 for row in visible_rows)
            axis_y.setRange(0, max(max_value * 1.1, 1))
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_y)
            chart.legend().setVisible(True)
            chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
            view = QChartView(chart)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setMinimumHeight(260)
            layout.addWidget(view)
            return container

        def _cash_flow_projection_chart(self, rows: list[Any]) -> QWidget:
            container = QWidget()
            layout = QVBoxLayout(container)
            if not rows or not any(row.accumulated_cents for row in rows):
                layout.addWidget(QLabel("Sem projecao de caixa para o periodo."))
                return container
            series = QLineSeries()
            series.setName("Saldo acumulado")
            values = [row.accumulated_cents / 100 for row in rows]
            for index, value in enumerate(values):
                series.append(index, value)
            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("Projecao de caixa acumulada")
            chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
            axis_x = QValueAxis()
            axis_x.setTitleText("Dias")
            axis_x.setLabelFormat("%d")
            axis_x.setRange(0, max(len(values) - 1, 1))
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)
            axis_y = QValueAxis()
            axis_y.setTitleText("R$")
            min_value = min(values)
            max_value = max(values)
            margin = max((max_value - min_value) * 0.1, 1)
            axis_y.setRange(min_value - margin, max_value + margin)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_y)
            chart.legend().setVisible(True)
            chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
            view = QChartView(chart)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setMinimumHeight(240)
            layout.addWidget(view)
            return container

        def _planning_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Planejamento")
            heading.setObjectName("heading")
            content.addWidget(heading)
            today = date.today()
            actions = QHBoxLayout()
            year_filter = QLineEdit(str(self._planning_year))
            year_filter.setPlaceholderText("Ano")
            month_filter = QComboBox()
            for month in range(1, 13):
                month_filter.addItem(f"{month:02d}", month)
            month_filter.setCurrentIndex(self._planning_month - 1)
            budget_button = QPushButton("Novo orcamento")
            budget_button.clicked.connect(self._create_budget_dialog)
            annual_budget_button = QPushButton("Orcamento anual")
            annual_budget_button.clicked.connect(self._create_annual_budget_dialog)
            rule_button = QPushButton("Nova regra")
            rule_button.clicked.connect(self._create_categorization_rule_dialog)
            filter_button = QPushButton("Atualizar")
            filter_button.clicked.connect(
                lambda: self._apply_planning_filters(year_filter, month_filter)
            )
            for widget in [
                QLabel("Ano"),
                year_filter,
                QLabel("Mes"),
                month_filter,
                filter_button,
                budget_button,
                annual_budget_button,
                rule_button,
            ]:
                actions.addWidget(widget)
            content.addLayout(actions)
            year = self._planning_year
            month = self._planning_month
            projection_start = today
            projection_end = today + timedelta(days=30)
            with connect(settings.database_path) as connection:
                comparison = get_budget_comparison(connection, year=year, month=month)
                annual_goals = get_annual_goal_comparison(connection, year=year)
                projection = get_cash_flow_projection(
                    connection,
                    start_date=projection_start,
                    end_date=projection_end,
                )
                rules = list_categorization_rules(connection)
            comparison_table = QTableWidget()
            comparison_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            comparison_table.setColumnCount(7)
            comparison_table.setHorizontalHeaderLabels(
                ["Categoria", "Tipo", "Centro", "Orcado", "Realizado", "Variacao", "%"]
            )
            comparison_table.setRowCount(len(comparison))
            for index, item in enumerate(comparison):
                percent = (
                    f"{(item.actual_cents / item.budgeted_cents) * 100:.1f}%"
                    if item.budgeted_cents
                    else "-"
                )
                values = [
                    item.category_name,
                    "Receita" if item.category_kind == "revenue" else "Despesa",
                    item.cost_center_name,
                    format_brl_cents(item.budgeted_cents),
                    format_brl_cents(item.actual_cents),
                    format_brl_cents(item.variance_cents),
                    percent,
                ]
                for column, value in enumerate(values):
                    comparison_table.setItem(index, column, QTableWidgetItem(value))
            content.addWidget(QLabel("Orcado vs realizado"))
            content.addWidget(comparison_table)
            annual_table = QTableWidget()
            annual_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            annual_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            annual_table.setColumnCount(8)
            annual_table.setHorizontalHeaderLabels(
                [
                    "Categoria",
                    "Tipo",
                    "Centro",
                    "Meta anual",
                    "Realizado",
                    "Variacao",
                    "%",
                    "Avanco",
                ]
            )
            annual_table.setRowCount(len(annual_goals))
            for index, annual_item in enumerate(annual_goals):
                values = [
                    annual_item.category_name,
                    "Receita" if annual_item.category_kind == "revenue" else "Despesa",
                    annual_item.cost_center_name,
                    format_brl_cents(annual_item.target_cents),
                    format_brl_cents(annual_item.actual_cents),
                    format_brl_cents(annual_item.variance_cents),
                    f"{annual_item.progress_percent}%" if annual_item.target_cents else "-",
                ]
                for column, value in enumerate(values):
                    annual_table.setItem(index, column, QTableWidgetItem(value))
                progress = QProgressBar()
                progress.setRange(0, 100)
                progress.setValue(min(annual_item.progress_percent, 100))
                annual_table.setCellWidget(index, 7, progress)
            content.addWidget(QLabel("Metas anuais"))
            content.addWidget(self._annual_goals_chart(annual_goals))
            content.addWidget(annual_table)
            projection_table = QTableWidget()
            projection_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            projection_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            projection_table.setColumnCount(5)
            projection_table.setHorizontalHeaderLabels(
                ["Data", "Entradas previstas", "Saidas previstas", "Saldo do dia", "Acumulado"]
            )
            visible_projection = [
                row
                for row in projection
                if row.expected_revenue_cents or row.expected_expense_cents
            ][:31]
            projection_table.setRowCount(len(visible_projection))
            for index, row in enumerate(visible_projection):
                values = [
                    row.projected_date.isoformat(),
                    format_brl_cents(row.expected_revenue_cents),
                    format_brl_cents(row.expected_expense_cents),
                    format_brl_cents(row.net_cents),
                    format_brl_cents(row.accumulated_cents),
                ]
                for column, value in enumerate(values):
                    projection_table.setItem(index, column, QTableWidgetItem(value))
            content.addWidget(QLabel("Projecao de fluxo de caixa - proximos 30 dias"))
            content.addWidget(self._cash_flow_projection_chart(projection))
            content.addWidget(projection_table)
            rules_table = QTableWidget()
            rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            rules_table.setColumnCount(7)
            rules_table.setHorizontalHeaderLabels(
                ["ID", "Palavra", "Tipo", "Categoria", "Centro", "Prioridade", "Ativa"]
            )
            rules_table.setRowCount(len(rules))
            for index, rule in enumerate(rules):
                values = [
                    str(rule["id"]),
                    str(rule["keyword"]),
                    "Todos" if rule["transaction_type"] is None else str(rule["transaction_type"]),
                    str(rule["category_name"]),
                    "" if rule["cost_center_name"] is None else str(rule["cost_center_name"]),
                    str(rule["priority"]),
                    "Sim" if rule["is_active"] else "Nao",
                ]
                for column, value in enumerate(values):
                    rules_table.setItem(index, column, QTableWidgetItem(value))
            content.addWidget(QLabel("Regras de categorizacao"))
            content.addWidget(rules_table)
            return page

        def _refresh_current_page(self) -> None:
            index = self.pages.currentIndex()
            current = self.pages.widget(index)
            if current is None:
                return
            self.pages.removeWidget(current)
            self.pages.insertWidget(index, self._wrap_page(self._page_for_index(index)))
            self.pages.setCurrentIndex(index)

        def _current_user_id(self) -> int:
            with connect(settings.database_path) as connection:
                user_id = get_session_user_id(connection, self._session_id)
            if user_id is None:
                raise ValueError("Sessao expirada. Entre novamente no sistema.")
            return user_id

        def _page_for_index(self, index: int) -> QWidget:
            if index == 0:
                return self._dashboard_page()
            if index == 1:
                return self._advanced_dashboard_page()
            if index == 2:
                return self._planning_page()
            if index == 3:
                return self._accounts_page()
            if index == 4:
                return self._transactions_page()
            if index == 5:
                return self._due_entries_page()
            if index == 6:
                return self._imports_page()
            if index == 7:
                return self._asaas_page()
            if index == 8:
                return self._sensitive_operations_page()
            if index == 9:
                return self._pdv_page()
            if index == 10:
                return self._purchases_page()
            if index == 11:
                return self._documents_page()
            if index == 12:
                return self._users_page()
            if index == 13:
                return self._audit_page()
            if index == 14:
                return self._backup_page()
            return self._settings_page()

        def _settings_page(self) -> QWidget:
            readiness = get_deployment_readiness(settings)
            database_health = None
            if readiness.database_backend == "sqlite":
                with connect(settings.database_path) as connection:
                    database_health = get_local_database_health(connection)
            page = QWidget()
            page.setObjectName("PageSurface")
            content = QVBoxLayout(page)
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(24)
            heading = QLabel("Configuracoes")
            heading.setObjectName("PageTitle")
            content.addWidget(heading)
            content.addWidget(
                build_section_header(
                    "Diagnostico de implantacao",
                    "Resumo tecnico do ambiente local, prontidao operacional "
                    "e artefatos de revisao.",
                )
            )

            table = FinancialTable(["Item", "Valor"])
            style_data_table(table, min_height=340)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            rows = [
                ("Ambiente", settings.app_env),
                ("Banco principal", readiness.database_backend),
                ("Local do banco", readiness.database_location),
                ("Modo offline", "Pronto" if readiness.offline_ready else "Pendente"),
                ("Uso em rede", "Pronto" if readiness.network_ready else "Pendente"),
                ("PostgreSQL", "Pronto" if readiness.postgres_ready else "Pendente"),
                (
                    "Escrita Asaas",
                    "Habilitada no .env local"
                    if settings.asaas_enable_write_operations
                    else "Desligada por padrao",
                ),
                (
                    "Chave Asaas",
                    "Configurada localmente" if settings.asaas_api_key else "Nao configurada",
                ),
                (
                    "PDV",
                    "Configurado localmente" if settings.pdv_database_url else "Nao configurado",
                ),
                (
                    "Google Sheets",
                    (
                        "Arquivos configurados localmente"
                        if settings.google_client_secret_path and settings.google_token_path
                        else "Nao configurado"
                    ),
                ),
            ]
            if database_health is not None:
                rows.extend(
                    [
                        (
                            "Schema local",
                            f"{database_health.schema_version}/"
                            f"{database_health.expected_schema_version}",
                        ),
                        (
                            "Integridade SQLite",
                            "OK" if database_health.quick_check_ok else "Revisar",
                        ),
                        (
                            "Chaves estrangeiras",
                            (
                                "OK"
                                if database_health.foreign_key_violations == 0
                                else f"{database_health.foreign_key_violations} violacoes"
                            ),
                        ),
                        (
                            "Jornal SQLite",
                            f"{database_health.journal_mode.upper()} "
                            f"({'OK' if database_health.wal_enabled else 'revisar'})",
                        ),
                        (
                            "Ensaio de migracao",
                            (
                                "Pronto"
                                if database_health.ready_for_migration_rehearsal
                                else "Pendente"
                            ),
                        ),
                    ]
                )
            table.setRowCount(len(rows))
            for row_index, (label, value) in enumerate(rows):
                add_table_cell(table, row_index, 0, label)
                add_table_cell(table, row_index, 1, value)
            settings_table_card = build_table_card(
                title="Estado atual do ambiente",
                caption=(
                    "Use este quadro para revisar rapidamente backend, "
                    "integracoes e preparo para fases futuras."
                ),
                table=table,
            )
            content.addWidget(settings_table_card)

            warnings = "\n".join(f"- {warning}" for warning in readiness.warnings)
            next_steps = "\n".join(f"- {step}" for step in readiness.next_steps)
            table_counts = ""
            if database_health is not None:
                table_counts = "\n\nTabelas criticas:\n" + "\n".join(
                    f"- {name}: {count}"
                    for name, count in database_health.critical_table_counts.items()
                )
            phase8_report_button = QPushButton("Exportar aceite local Fase 8")
            phase8_report_button.clicked.connect(
                lambda: self._export_phase8_acceptance_report(readiness, database_health)
            )
            content.addWidget(phase8_report_button)
            phase8_package_button = QPushButton("Exportar pacote Fase 8")
            phase8_package_button.clicked.connect(
                lambda: self._export_phase8_evidence_package(readiness, database_health)
            )
            content.addWidget(phase8_package_button)
            phase8_verify_button = QPushButton("Verificar pacote Fase 8")
            phase8_verify_button.clicked.connect(self._verify_phase8_evidence_package)
            content.addWidget(phase8_verify_button)
            phase8_summary_button = QPushButton("Exportar resumo Fase 8")
            phase8_summary_button.clicked.connect(self._export_phase8_evidence_summary)
            content.addWidget(phase8_summary_button)
            phase8_finalize_button = QPushButton("Finalizar Fase 8")
            phase8_finalize_button.clicked.connect(self._export_phase8_finalization)
            content.addWidget(phase8_finalize_button)
            export_button = QPushButton("Exportar roteiro de migracao")
            export_button.clicked.connect(
                lambda: self._export_migration_rehearsal_plan(readiness, database_health)
            )
            content.addWidget(export_button)
            network_readiness_button = QPushButton("Exportar prontidao de rede")
            network_readiness_button.clicked.connect(
                lambda: self._export_network_readiness(readiness, database_health)
            )
            content.addWidget(network_readiness_button)
            network_package_button = QPushButton("Exportar pacote de rede")
            network_package_button.clicked.connect(
                lambda: self._export_network_rehearsal_package(readiness, database_health)
            )
            content.addWidget(network_package_button)
            network_verify_button = QPushButton("Verificar pacote de rede")
            network_verify_button.clicked.connect(self._verify_network_rehearsal_package)
            content.addWidget(network_verify_button)
            network_summary_button = QPushButton("Exportar resumo de rede")
            network_summary_button.clicked.connect(self._export_network_rehearsal_summary)
            content.addWidget(network_summary_button)
            inventory_button = QPushButton("Exportar inventario de schema")
            inventory_button.setEnabled(database_health is not None)
            inventory_button.clicked.connect(
                lambda: self._export_schema_inventory(readiness, database_health)
            )
            content.addWidget(inventory_button)
            compatibility_button = QPushButton("Exportar compatibilidade PostgreSQL")
            compatibility_button.setEnabled(database_health is not None)
            compatibility_button.clicked.connect(
                lambda: self._export_postgres_compatibility_report(readiness, database_health)
            )
            content.addWidget(compatibility_button)
            load_plan_button = QPushButton("Exportar plano de carga PostgreSQL")
            load_plan_button.setEnabled(database_health is not None)
            load_plan_button.clicked.connect(
                lambda: self._export_postgres_load_plan(readiness, database_health)
            )
            content.addWidget(load_plan_button)
            adapter_contract_button = QPushButton("Exportar contrato adapter PostgreSQL")
            adapter_contract_button.setEnabled(database_health is not None)
            adapter_contract_button.clicked.connect(
                lambda: self._export_postgres_adapter_contract(readiness, database_health)
            )
            content.addWidget(adapter_contract_button)
            execution_plan_button = QPushButton("Exportar plano de execucao PostgreSQL")
            execution_plan_button.setEnabled(database_health is not None)
            execution_plan_button.clicked.connect(
                lambda: self._export_postgres_execution_plan(readiness, database_health)
            )
            content.addWidget(execution_plan_button)
            preflight_button = QPushButton("Exportar preflight runner PostgreSQL")
            preflight_button.setEnabled(database_health is not None)
            preflight_button.clicked.connect(
                lambda: self._export_postgres_rehearsal_preflight(readiness, database_health)
            )
            content.addWidget(preflight_button)
            runner_readiness_button = QPushButton("Exportar prontidao runner PostgreSQL")
            runner_readiness_button.setEnabled(database_health is not None)
            runner_readiness_button.clicked.connect(
                lambda: self._export_postgres_runner_readiness(readiness, database_health)
            )
            content.addWidget(runner_readiness_button)
            blueprint_button = QPushButton("Exportar blueprint PostgreSQL")
            blueprint_button.setEnabled(database_health is not None)
            blueprint_button.clicked.connect(
                lambda: self._export_postgres_schema_blueprint(readiness, database_health)
            )
            content.addWidget(blueprint_button)
            package_button = QPushButton("Exportar pacote de homologacao PostgreSQL")
            package_button.setEnabled(database_health is not None)
            package_button.clicked.connect(
                lambda: self._export_postgres_rehearsal_package(readiness, database_health)
            )
            content.addWidget(package_button)
            postgres_verify_button = QPushButton("Verificar pacote PostgreSQL")
            postgres_verify_button.clicked.connect(self._verify_postgres_rehearsal_package)
            content.addWidget(postgres_verify_button)
            postgres_summary_button = QPushButton("Exportar resumo PostgreSQL")
            postgres_summary_button.clicked.connect(self._export_postgres_rehearsal_summary)
            content.addWidget(postgres_summary_button)
            details = QPlainTextEdit()
            details.setReadOnly(True)
            details.setPlainText(
                "Avisos:\n"
                f"{warnings if warnings else '- Nenhum aviso'}\n\n"
                "Proximos passos para rede/PostgreSQL:\n"
                f"{next_steps if next_steps else '- Nenhum passo pendente'}"
                f"{table_counts}"
            )
            content.addWidget(details)
            return page

        def _export_phase8_acceptance_report(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            default_path = settings.paths.documents_dir / "exports" / "aceite-local-fase-8.md"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar aceite local Fase 8",
                str(default_path),
                "Markdown (*.md)",
            )
            if not path:
                return
            inventory = None
            if database_health is not None:
                with connect(settings.database_path) as connection:
                    inventory = get_local_schema_inventory(connection)
            report = build_phase8_local_acceptance_report_markdown(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding="utf-8")
            QMessageBox.information(
                self,
                "Aceite local exportado",
                "Relatorio local da Fase 8 exportado sem dados sensiveis.",
            )

        def _export_phase8_evidence_package(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            default_path = settings.paths.documents_dir / "exports" / "pacote-evidencias-fase-8.zip"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar pacote Fase 8",
                str(default_path),
                "ZIP (*.zip)",
            )
            if not path:
                return
            inventory = None
            if database_health is not None:
                with connect(settings.database_path) as connection:
                    inventory = get_local_schema_inventory(connection)
            write_phase8_local_evidence_package(
                output_path=Path(path),
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            QMessageBox.information(
                self,
                "Pacote Fase 8 exportado",
                "Pacote local de evidencias da Fase 8 exportado sem dados sensiveis.",
            )

        def _verify_phase8_evidence_package(self) -> None:
            default_path = settings.paths.documents_dir / "exports" / "pacote-evidencias-fase-8.zip"
            package_path_text, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar pacote Fase 8",
                str(default_path),
                "ZIP (*.zip)",
            )
            if not package_path_text:
                return
            default_output_path = (
                settings.paths.documents_dir / "exports" / "verificacao-pacote-fase-8.json"
            )
            output_path_text, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar verificacao Fase 8",
                str(default_output_path),
                "JSON (*.json)",
            )
            if not output_path_text:
                return
            payload = build_phase8_local_evidence_package_verification_json(
                package_path=Path(package_path_text),
            )
            parsed = json.loads(payload)
            output_path = Path(output_path_text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            message = (
                "Pacote Fase 8 pronto para revisao."
                if parsed["ready_for_review"]
                else "Pacote Fase 8 bloqueado; revise o JSON exportado."
            )
            QMessageBox.information(self, "Verificacao Fase 8", message)

        def _export_phase8_evidence_summary(self) -> None:
            default_path = settings.paths.documents_dir / "exports" / "pacote-evidencias-fase-8.zip"
            package_path_text, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar pacote Fase 8",
                str(default_path),
                "ZIP (*.zip)",
            )
            if not package_path_text:
                return
            output_path_text, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar resumo Fase 8",
                str(settings.paths.documents_dir / "exports" / "resumo-aceite-fase-8.md"),
                "Markdown (*.md)",
            )
            if not output_path_text:
                return
            summary = build_phase8_local_evidence_review_summary_markdown(
                package_path=Path(package_path_text),
            )
            output_path = Path(output_path_text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(summary, encoding="utf-8")
            QMessageBox.information(
                self,
                "Resumo Fase 8 exportado",
                "Resumo de aceite da Fase 8 exportado sem dados sensiveis.",
            )

        def _export_phase8_finalization(self) -> None:
            exports_dir = settings.paths.documents_dir / "exports"
            asaas_verification_text = self._select_phase8_final_file(
                "Selecionar verificacao Asaas",
                exports_dir / "verificacao-pacote-asaas.json",
                "JSON (*.json)",
            )
            if not asaas_verification_text:
                return
            asaas_summary_text = self._select_phase8_final_file(
                "Selecionar resumo Asaas",
                exports_dir / "resumo-aceite-asaas.md",
                "Markdown (*.md)",
            )
            if not asaas_summary_text:
                return
            postgres_verification_text = self._select_phase8_final_file(
                "Selecionar verificacao PostgreSQL",
                exports_dir / "verificacao-pacote-postgresql.json",
                "JSON (*.json)",
            )
            if not postgres_verification_text:
                return
            postgres_report_text = self._select_phase8_final_file(
                "Selecionar relatorio PostgreSQL",
                exports_dir / "relatorio-homologacao-postgresql.md",
                "Markdown (*.md)",
            )
            if not postgres_report_text:
                return
            phase8_verification_text = self._select_phase8_final_file(
                "Selecionar verificacao Fase 8",
                exports_dir / "verificacao-pacote-fase-8.json",
                "JSON (*.json)",
            )
            if not phase8_verification_text:
                return
            output_dir_text = QFileDialog.getExistingDirectory(
                self,
                "Selecionar pasta final da Fase 8",
                str(exports_dir),
            )
            if not output_dir_text:
                return
            output_dir = Path(output_dir_text)
            readiness_path = output_dir / "prontidao-fechamento-fase-8.json"
            closeout_path = output_dir / "encerramento-fase-8.md"
            package_path = output_dir / "pacote-encerramento-fase-8.zip"
            payload = build_phase8_closure_readiness_json(
                asaas_verification_path=Path(asaas_verification_text),
                asaas_summary_path=Path(asaas_summary_text),
                postgres_package_verification_path=Path(postgres_verification_text),
                postgres_rehearsal_report_path=Path(postgres_report_text),
                phase8_package_verification_path=Path(phase8_verification_text),
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            readiness_path.write_text(payload, encoding="utf-8")
            closeout_path.write_text(
                build_phase8_closeout_report_markdown(
                    closure_readiness_path=readiness_path,
                ),
                encoding="utf-8",
            )
            write_phase8_closeout_package(
                closure_readiness_path=readiness_path,
                closeout_report_path=closeout_path,
                output_path=package_path,
            )
            ready_to_close = json.loads(payload)["ready_to_close_phase8"]
            message = (
                "Artefatos finais da Fase 8 gerados e prontos para fechamento."
                if ready_to_close
                else "Artefatos finais gerados, mas a Fase 8 ainda esta pendente."
            )
            QMessageBox.information(self, "Finalizacao Fase 8", message)

        def _select_phase8_final_file(
            self,
            title: str,
            default_path: Path,
            file_filter: str,
        ) -> str:
            path_text, _ = QFileDialog.getOpenFileName(
                self,
                title,
                str(default_path),
                file_filter,
            )
            return path_text

        def _export_migration_rehearsal_plan(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            default_path = (
                settings.paths.documents_dir / "exports" / "roteiro-migracao-postgresql.md"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar roteiro de migracao",
                str(default_path),
                "Markdown (*.md)",
            )
            if not path:
                return
            plan = build_migration_rehearsal_plan(
                settings=settings,
                readiness=readiness,
                health=database_health,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(plan, encoding="utf-8")
            QMessageBox.information(
                self,
                "Roteiro exportado",
                "Roteiro de ensaio de migracao exportado localmente.",
            )

        def _export_network_readiness(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            default_path = settings.paths.documents_dir / "exports" / "prontidao-uso-em-rede.json"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar prontidao de rede",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            payload = build_network_readiness_json(
                settings=settings,
                readiness=readiness,
                health=database_health,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            QMessageBox.information(
                self,
                "Prontidao exportada",
                "Prontidao de rede exportada localmente sem conexao externa.",
            )

        def _export_network_rehearsal_package(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            default_path = settings.paths.documents_dir / "exports" / "pacote-homologacao-rede.zip"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar pacote de rede",
                str(default_path),
                "ZIP (*.zip)",
            )
            if not path:
                return
            write_network_rehearsal_package(
                output_path=Path(path),
                settings=settings,
                readiness=readiness,
                health=database_health,
            )
            QMessageBox.information(
                self,
                "Pacote exportado",
                "Pacote de rede exportado localmente com manifesto e hashes.",
            )

        def _verify_network_rehearsal_package(self) -> None:
            default_package = (
                settings.paths.documents_dir / "exports" / "pacote-homologacao-rede.zip"
            )
            package_path_text, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar pacote de rede",
                str(default_package),
                "ZIP (*.zip)",
            )
            if not package_path_text:
                return
            default_output = (
                settings.paths.documents_dir / "exports" / "verificacao-pacote-rede.json"
            )
            output_path_text, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar verificacao de rede",
                str(default_output),
                "JSON (*.json)",
            )
            if not output_path_text:
                return
            payload = build_network_rehearsal_package_verification_json(
                package_path=Path(package_path_text),
            )
            parsed = json.loads(payload)
            output_path = Path(output_path_text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            QMessageBox.information(
                self,
                "Verificacao exportada",
                (
                    "Pacote de rede pronto para revisao."
                    if parsed["ready_for_review"]
                    else "Pacote de rede bloqueado; revise o JSON exportado."
                ),
            )

        def _export_network_rehearsal_summary(self) -> None:
            default_package = (
                settings.paths.documents_dir / "exports" / "pacote-homologacao-rede.zip"
            )
            package_path_text, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar pacote de rede",
                str(default_package),
                "ZIP (*.zip)",
            )
            if not package_path_text:
                return
            default_output = settings.paths.documents_dir / "exports" / "resumo-aceite-rede.md"
            output_path_text, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar resumo de rede",
                str(default_output),
                "Markdown (*.md)",
            )
            if not output_path_text:
                return
            summary = build_network_rehearsal_review_summary_markdown(
                package_path=Path(package_path_text),
            )
            output_path = Path(output_path_text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(summary, encoding="utf-8")
            QMessageBox.information(
                self,
                "Resumo exportado",
                "Resumo de aceite de rede exportado sem dados sensiveis.",
            )

        def _export_schema_inventory(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Inventario indisponivel",
                    "Inventario de schema local esta disponivel apenas para SQLite.",
                )
                return
            default_path = (
                settings.paths.documents_dir / "exports" / "inventario-schema-sqlite.json"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar inventario de schema",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            payload = build_schema_inventory_json(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            QMessageBox.information(
                self,
                "Inventario exportado",
                "Inventario de schema exportado localmente.",
            )

        def _export_postgres_compatibility_report(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Relatorio indisponivel",
                    "Relatorio de compatibilidade esta disponivel apenas para SQLite.",
                )
                return
            default_path = (
                settings.paths.documents_dir / "exports" / "compatibilidade-postgresql.md"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar compatibilidade PostgreSQL",
                str(default_path),
                "Markdown (*.md)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            report = build_postgres_compatibility_report(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding="utf-8")
            QMessageBox.information(
                self,
                "Relatorio exportado",
                "Relatorio de compatibilidade PostgreSQL exportado localmente.",
            )

        def _export_postgres_load_plan(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Plano indisponivel",
                    "Plano de carga esta disponivel apenas para SQLite.",
                )
                return
            default_path = settings.paths.documents_dir / "exports" / "plano-carga-postgresql.json"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar plano de carga PostgreSQL",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            load_plan = build_postgres_load_plan_json(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(load_plan, encoding="utf-8")
            QMessageBox.information(
                self,
                "Plano exportado",
                "Plano de carga PostgreSQL exportado localmente.",
            )

        def _export_postgres_adapter_contract(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Contrato indisponivel",
                    "Contrato do adapter esta disponivel apenas para SQLite.",
                )
                return
            default_path = (
                settings.paths.documents_dir / "exports" / "contrato-adapter-postgresql.json"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar contrato adapter PostgreSQL",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            contract = build_postgres_adapter_contract_json(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(contract, encoding="utf-8")
            QMessageBox.information(
                self,
                "Contrato exportado",
                "Contrato do adapter PostgreSQL exportado localmente.",
            )

        def _export_postgres_execution_plan(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Plano indisponivel",
                    "Plano de execucao esta disponivel apenas para SQLite.",
                )
                return
            default_path = (
                settings.paths.documents_dir
                / "exports"
                / "plano-execucao-homologacao-postgresql.json"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar plano de execucao PostgreSQL",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            plan = build_postgres_rehearsal_execution_plan_json(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(plan, encoding="utf-8")
            QMessageBox.information(
                self,
                "Plano exportado",
                "Plano de execucao PostgreSQL exportado localmente.",
            )

        def _export_postgres_rehearsal_preflight(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Preflight indisponivel",
                    "Preflight do runner esta disponivel apenas para SQLite.",
                )
                return
            default_path = (
                settings.paths.documents_dir
                / "exports"
                / "preflight-runner-homologacao-postgresql.json"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar preflight runner PostgreSQL",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            preflight = build_postgres_rehearsal_preflight_json(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(preflight, encoding="utf-8")
            QMessageBox.information(
                self,
                "Preflight exportado",
                "Preflight offline do runner PostgreSQL exportado localmente.",
            )

        def _export_postgres_runner_readiness(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Prontidao indisponivel",
                    "Prontidao do runner esta disponivel apenas para SQLite.",
                )
                return
            default_path = (
                settings.paths.documents_dir
                / "exports"
                / "prontidao-runner-homologacao-postgresql.json"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar prontidao runner PostgreSQL",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            payload = build_postgres_rehearsal_runner_readiness_json(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            QMessageBox.information(
                self,
                "Prontidao exportada",
                "Prontidao opt-in do runner PostgreSQL exportada localmente.",
            )

        def _export_postgres_schema_blueprint(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Blueprint indisponivel",
                    "Blueprint PostgreSQL esta disponivel apenas para SQLite.",
                )
                return
            default_path = settings.paths.documents_dir / "exports" / "blueprint-postgresql.sql"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar blueprint PostgreSQL",
                str(default_path),
                "SQL (*.sql)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            blueprint = build_postgres_schema_blueprint(
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(blueprint, encoding="utf-8")
            QMessageBox.information(
                self,
                "Blueprint exportado",
                "Blueprint PostgreSQL exportado localmente para revisao tecnica.",
            )

        def _export_postgres_rehearsal_package(
            self,
            readiness: DeploymentReadiness,
            database_health: LocalDatabaseHealth | None,
        ) -> None:
            if database_health is None:
                QMessageBox.warning(
                    self,
                    "Pacote indisponivel",
                    "Pacote de homologacao esta disponivel apenas para SQLite.",
                )
                return
            default_path = (
                settings.paths.documents_dir / "exports" / "pacote-homologacao-postgresql.zip"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar pacote de homologacao PostgreSQL",
                str(default_path),
                "ZIP (*.zip)",
            )
            if not path:
                return
            with connect(settings.database_path) as connection:
                inventory = get_local_schema_inventory(connection)
            write_postgres_rehearsal_package(
                output_path=Path(path),
                settings=settings,
                readiness=readiness,
                health=database_health,
                inventory=inventory,
            )
            QMessageBox.information(
                self,
                "Pacote exportado",
                "Pacote PostgreSQL exportado localmente com manifesto e hashes.",
            )

        def _verify_postgres_rehearsal_package(self) -> None:
            default_path = (
                settings.paths.documents_dir / "exports" / "pacote-homologacao-postgresql.zip"
            )
            package_path_text, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar pacote PostgreSQL",
                str(default_path),
                "ZIP (*.zip)",
            )
            if not package_path_text:
                return
            default_output_path = (
                settings.paths.documents_dir / "exports" / "verificacao-pacote-postgresql.json"
            )
            output_path_text, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar verificacao PostgreSQL",
                str(default_output_path),
                "JSON (*.json)",
            )
            if not output_path_text:
                return
            payload = build_postgres_rehearsal_package_verification_json(
                package_path=Path(package_path_text),
            )
            parsed = json.loads(payload)
            output_path = Path(output_path_text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            message = (
                "Pacote PostgreSQL pronto para revisao."
                if parsed["ready_for_review"]
                else "Pacote PostgreSQL bloqueado; revise o JSON exportado."
            )
            QMessageBox.information(self, "Verificacao PostgreSQL", message)

        def _export_postgres_rehearsal_summary(self) -> None:
            default_path = (
                settings.paths.documents_dir / "exports" / "pacote-homologacao-postgresql.zip"
            )
            package_path_text, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar pacote PostgreSQL",
                str(default_path),
                "ZIP (*.zip)",
            )
            if not package_path_text:
                return
            output_path_text, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar resumo PostgreSQL",
                str(settings.paths.documents_dir / "exports" / "resumo-aceite-postgresql.md"),
                "Markdown (*.md)",
            )
            if not output_path_text:
                return
            summary = build_postgres_rehearsal_review_summary_markdown(
                package_path=Path(package_path_text),
            )
            output_path = Path(output_path_text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(summary, encoding="utf-8")
            QMessageBox.information(
                self,
                "Resumo PostgreSQL exportado",
                "Resumo de aceite PostgreSQL exportado sem dados sensiveis.",
            )

        def _users_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Usuarios e perfis")
            heading.setObjectName("heading")
            content.addWidget(heading)
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["ID", "Usuario", "Perfil", "Ativo", "Falhas"])
            with connect(settings.database_path) as connection:
                rows = list_users(connection)
                roles = ", ".join(row["name"] for row in list_roles(connection))
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                values = [
                    str(row["id"]),
                    str(row["username"]),
                    str(row["role"]),
                    "Sim" if row["is_active"] else "Nao",
                    str(row["failed_attempts"]),
                ]
                for column, value in enumerate(values):
                    table.setItem(index, column, QTableWidgetItem(value))
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            content.addWidget(QLabel(f"Perfis configurados: {roles}"))
            content.addWidget(table)
            return page

        def _due_entries_page(self) -> QWidget:
            page = QWidget()
            page.setObjectName("PageSurface")
            content = QVBoxLayout(page)
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(24)
            heading = QLabel("Pagar e receber")
            heading.setObjectName("PageTitle")
            content.addWidget(heading)

            action_card, action_layout = build_section_card()
            action_layout.addWidget(
                build_section_header(
                    "Acoes rapidas",
                    "Registre contas a pagar e a receber sem perder contexto do historico.",
                )
            )
            action_row, actions = build_responsive_button_row()
            for index, (label, handler, variant) in enumerate(
                [
                    ("Nova conta a pagar", lambda: self._create_due_entry("payable"), "secondary"),
                    (
                        "Nova conta a receber",
                        lambda: self._create_due_entry("receivable"),
                        "primary",
                    ),
                ]
            ):
                button = make_button(label, variant=variant, icon_text="+")
                button.clicked.connect(handler)
                actions.addWidget(button, 0, index)
            action_layout.addWidget(action_row)
            content.addWidget(action_card)

            table = FinancialTable(
                ["", "Data", "Descricao", "Categoria", "Conta", "Valor", "Status"]
            )
            style_data_table(table, min_height=340)
            settle_button = make_button("Baixar selecionado", variant="secondary")
            settle_button.clicked.connect(lambda: self._settle_selected_due_entry(table))
            cancel_button = make_button("Cancelar selecionado", variant="danger")
            cancel_button.clicked.connect(lambda: self._cancel_selected_due_entry(table))
            action_buttons = QHBoxLayout()
            action_buttons.addWidget(settle_button)
            action_buttons.addWidget(cancel_button)
            action_buttons.addStretch(1)
            content.addLayout(action_buttons)

            filters = QGridLayout()
            filters.setHorizontalSpacing(12)
            filters.setVerticalSpacing(12)
            type_filter = QComboBox()
            type_filter.addItem("Todos tipos", None)
            type_filter.addItem("Pagar", "payable")
            type_filter.addItem("Receber", "receivable")
            category_filter = QComboBox()
            cost_center_filter = QComboBox()
            status_filter = QComboBox()
            status_filter.addItem("Todos status", None)
            for label, value in [
                ("Aberto", "open"),
                ("Parcial", "partial"),
                ("Pago", "paid"),
                ("Cancelado", "canceled"),
            ]:
                status_filter.addItem(label, value)
            with connect(settings.database_path) as connection:
                _fill_filter_combo(category_filter, list_categories(connection), "Todas categorias")
                _fill_filter_combo(
                    cost_center_filter,
                    list_cost_centers(connection),
                    "Todos centros",
                )
            for widget in [type_filter, category_filter, cost_center_filter, status_filter]:
                filters.addWidget(widget)
            filter_button = make_button("Filtrar", variant="secondary")
            filters.addWidget(filter_button)
            content.addLayout(filters)

            def load_table() -> None:
                with connect(settings.database_path) as connection:
                    rows = list_payable_receivable_entries(
                        connection,
                        today=date.today(),
                        entry_type=_optional_combo_text(type_filter),
                        category_id=_optional_combo_id(category_filter),
                        cost_center_id=_optional_combo_id(cost_center_filter),
                        status=_optional_combo_text(status_filter),
                    )
                if not rows:
                    table.set_empty_message(
                        "Nenhum titulo encontrado.",
                        "Ajuste os filtros ou registre um novo item.",
                    )
                    return
                table.clearSpans()
                table.setRowCount(len(rows))
                for index, row in enumerate(rows):
                    entry_type = str(row["entry_type"])
                    open_amount = _dict_int(row, "open_amount_cents")
                    signed_value = open_amount if entry_type == "receivable" else -open_amount
                    table.setCellWidget(index, 0, _build_row_checkbox_widget())
                    add_table_cell(table, index, 1, str(row["due_date"]))
                    due_date_item = table.item(index, 1)
                    if due_date_item is not None:
                        due_date_item.setData(Qt.ItemDataRole.UserRole, _dict_int(row, "id"))
                    add_table_cell(table, index, 2, str(row["description"]))
                    add_table_cell(
                        table,
                        index,
                        3,
                        "" if row["category_name"] is None else str(row["category_name"]),
                    )
                    add_table_cell(
                        table,
                        index,
                        4,
                        "" if row["account_name"] is None else str(row["account_name"]),
                    )
                    value_label = QLabel(_format_signed_brl(signed_value))
                    value_label.setStyleSheet(
                        f"QLabel {{ color: {COLORS.green if signed_value >= 0 else COLORS.red}; "
                        "font-family: Consolas, 'Cascadia Mono'; "
                        "font-size: 13px; font-weight: 600; background: transparent; }}"
                    )
                    table.setCellWidget(index, 5, _right_aligned_widget(value_label))
                    badge = _due_entry_badge(
                        entry_type=entry_type,
                        effective_status=str(row["effective_status"]),
                        due_date=str(row["due_date"]),
                    )
                    table.setCellWidget(index, 6, _centered_widget(badge))

            filter_button.clicked.connect(load_table)
            load_table()
            due_table_card = build_table_card(
                title="Titulos em aberto e historico",
                caption="Estrutura preparada para muitos registros e acompanhamento operacional.",
                table=table,
            )
            content.addWidget(due_table_card)
            return page

        def _accounts_page(self) -> QWidget:
            page = QWidget()
            page.setObjectName("PageSurface")
            content = QVBoxLayout(page)
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(24)
            heading = QLabel("Contas")
            heading.setObjectName("PageTitle")
            content.addWidget(heading)

            with connect(settings.database_path) as connection:
                rows = list_financial_accounts(connection)

            header_card, header_layout = build_section_card()
            summary = QLabel(
                "Cadastre e acompanhe contas bancarias, caixa e integracoes financeiras."
            )
            summary.setObjectName("SectionCaption")
            create_button = make_button("Nova conta", variant="secondary", icon_text="+")
            create_button.clicked.connect(self._create_account)
            header_layout.addWidget(summary)
            header_layout.addWidget(create_button, alignment=Qt.AlignmentFlag.AlignLeft)
            content.addWidget(header_card)

            if not rows:
                empty_cta = make_button("Nova conta", variant="secondary", icon_text="+")
                empty_cta.clicked.connect(self._create_account)
                content.addWidget(
                    EmptyState(
                        icon_text="◧",
                        title="Nenhuma conta cadastrada",
                        description="Adicione uma conta bancaria para comecar.",
                        cta=empty_cta,
                    )
                )
                return page

            table = FinancialTable(["", "Nome", "Tipo", "Saldo atual", "Status", "Data saldo"])
            style_data_table(table, min_height=300)
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                table.setCellWidget(index, 0, _build_row_checkbox_widget())
                add_table_cell(table, index, 1, str(row["name"]))
                add_table_cell(table, index, 2, _account_type_label(str(row["account_type"])))
                add_table_cell(
                    table,
                    index,
                    3,
                    format_brl_cents(int(row["current_balance_cents"])),
                    align_right=True,
                )
                status_tone = "paid" if str(row["status"]) == "active" else "cancelled"
                table.setCellWidget(
                    index,
                    4,
                    _centered_widget(
                        BadgeLabel(
                            _account_status_label(str(row["status"])),
                            status_tone,
                            show_dot=False,
                        )
                    ),
                )
                add_table_cell(table, index, 5, str(row["balance_date"]))
            accounts_table_card = build_table_card(
                title="Contas cadastradas",
                caption="Acompanhe o status e o saldo base das contas conectadas ao financeiro.",
                table=table,
            )
            content.addWidget(accounts_table_card)
            return page

        def _transactions_page(self) -> QWidget:
            page = QWidget()
            page.setObjectName("PageSurface")
            content = QVBoxLayout(page)
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(24)
            heading = QLabel("Lancamentos")
            heading.setObjectName("PageTitle")
            content.addWidget(heading)

            action_card, action_layout = build_section_card()
            action_layout.addWidget(
                build_section_header(
                    "Acoes rapidas",
                    "Registre receitas, despesas e transferencias sem perder "
                    "contexto do historico.",
                )
            )
            action_row, actions = build_responsive_button_row()
            primary_actions = [
                ("Nova receita", self._create_revenue, "secondary", "+"),
                ("Nova despesa", self._create_expense, "primary", "+"),
                ("Transferir", self._create_transfer, "secondary", "⇄"),
                ("Nova categoria", self._create_category, "ghost", None),
                ("Novo centro", self._create_cost_center, "ghost", None),
            ]
            for index, (label, handler, variant, icon_text) in enumerate(primary_actions):
                button = make_button(label, variant=variant, icon_text=icon_text)
                button.clicked.connect(handler)
                actions.addWidget(button, index // 3, index % 3)
            action_layout.addWidget(action_row)
            content.addWidget(action_card)

            rail_card, rail_layout = build_muted_section_card()
            rail_layout.addWidget(
                build_section_header(
                    "Filtros e navegacao",
                    "Combine tabs e filtros para manter a leitura clara mesmo "
                    "com volume maior de dados.",
                )
            )

            tabs_row, type_tabs_layout = build_responsive_button_row()
            type_tabs: list[tuple[str, str]] = [
                ("Todos", "all"),
                ("Receitas", "revenue"),
                ("Despesas", "expense"),
                ("Transferencias", "transfer"),
            ]
            period_tabs: list[tuple[str, str]] = [
                ("Esta semana", "week"),
                ("Este mes", "month"),
                ("Este ano", "year"),
                ("Personalizado", "custom"),
            ]
            type_buttons: dict[str, Any] = {}
            period_buttons: dict[str, Any] = {}
            for index, (label, value) in enumerate(type_tabs):
                button = make_filter_button(label, active=self._transaction_tab == value)
                button.clicked.connect(
                    lambda _checked=False, current=value: self._set_transaction_tab(current)
                )
                type_tabs_layout.addWidget(button, 0, index)
                type_buttons[value] = button
            rail_layout.addWidget(tabs_row)

            period_row, period_tabs_layout = build_responsive_button_row()
            for index, (label, value) in enumerate(period_tabs):
                button = make_filter_button(label, active=self._transaction_period == value)
                button.clicked.connect(
                    lambda _checked=False, current=value: self._set_transaction_period(current)
                )
                period_tabs_layout.addWidget(button, 0, index)
                period_buttons[value] = button
            rail_layout.addWidget(period_row)

            filters = QGridLayout()
            filters.setHorizontalSpacing(12)
            filters.setVerticalSpacing(12)
            type_filter = QComboBox()
            type_filter.addItem("Todos tipos", None)
            for label, value in [
                ("Receita", "revenue"),
                ("Despesa", "expense"),
                ("Transferencia entrada", "transfer_in"),
                ("Transferencia saida", "transfer_out"),
            ]:
                type_filter.addItem(label, value)
            category_filter = QComboBox()
            cost_center_filter = QComboBox()
            with connect(settings.database_path) as connection:
                _fill_filter_combo(category_filter, list_categories(connection), "Todas categorias")
                _fill_filter_combo(
                    cost_center_filter,
                    list_cost_centers(connection),
                    "Todos centros",
                )
            filters.addWidget(_field_label("Tipo"), 0, 0)
            filters.addWidget(type_filter, 1, 0)
            filters.addWidget(_field_label("Categoria"), 0, 1)
            filters.addWidget(category_filter, 1, 1)
            filters.addWidget(_field_label("Centro"), 0, 2)
            filters.addWidget(cost_center_filter, 1, 2)
            filter_button = make_button("Filtrar", variant="secondary")
            filters.addWidget(filter_button, 1, 3)
            rail_layout.addLayout(filters)
            content.addWidget(rail_card)

            table = FinancialTable(
                ["", "Data", "Descricao", "Categoria", "Conta", "Valor", "Status"]
            )
            style_data_table(table, min_height=360)
            cancel_button = make_button("Cancelar selecionado", variant="danger")
            cancel_button.clicked.connect(lambda: self._cancel_selected_transaction(table))
            table_card, table_layout = build_section_card()
            table_layout.addWidget(
                build_section_header(
                    "Historico financeiro",
                    "Leitura preparada para muitos registros, valores longos "
                    "e acompanhamento operacional diario.",
                )
            )
            table_actions = QHBoxLayout()
            table_actions.addStretch(1)
            table_actions.addWidget(cancel_button)
            table_layout.addLayout(table_actions)
            table_layout.addWidget(table)

            empty_state_ref: dict[str, QWidget | None] = {"widget": None}

            def load_table() -> None:
                if empty_state_ref["widget"] is not None:
                    empty_state_ref["widget"].setParent(None)
                    empty_state_ref["widget"] = None
                with connect(settings.database_path) as connection:
                    rows = list_financial_transactions(
                        connection,
                        transaction_type=_optional_combo_text(type_filter),
                        category_id=_optional_combo_id(category_filter),
                        cost_center_id=_optional_combo_id(cost_center_filter),
                    )
                filtered_rows = _filter_transaction_rows(
                    rows,
                    transaction_tab=self._transaction_tab,
                    period=self._transaction_period,
                    today=date.today(),
                )
                if not filtered_rows:
                    empty_cta = make_button("Nova receita", variant="primary", icon_text="+")
                    empty_cta.clicked.connect(self._create_revenue)
                    empty_state = EmptyState(
                        icon_text="::",
                        title="Nenhum lancamento encontrado",
                        description=(
                            "Crie o primeiro lancamento ou ajuste os filtros para "
                            "ampliar o recorte."
                        ),
                        cta=empty_cta,
                    )
                    table.hide()
                    table_layout.addWidget(empty_state)
                    empty_state_ref["widget"] = empty_state
                    return
                table.show()
                table.clearSpans()
                table.setRowCount(len(filtered_rows))
                for index, row in enumerate(filtered_rows):
                    transaction_type = str(row["transaction_type"])
                    amount_cents = int(row["amount_cents"])
                    signed_value = _transaction_signed_value(transaction_type, amount_cents)
                    table.setCellWidget(index, 0, _build_row_checkbox_widget())
                    add_table_cell(table, index, 1, str(row["effective_date"]))
                    effective_date_item = table.item(index, 1)
                    if effective_date_item is not None:
                        effective_date_item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
                    add_table_cell(table, index, 2, str(row["description"]))
                    add_table_cell(
                        table,
                        index,
                        3,
                        "" if row["category_name"] is None else str(row["category_name"]),
                    )
                    add_table_cell(table, index, 4, str(row["account_name"]))
                    value_label = QLabel(_format_signed_brl(signed_value))
                    value_label.setStyleSheet(
                        f"QLabel {{ color: {_transaction_value_color(transaction_type)}; "
                        "font-family: Consolas, 'Cascadia Mono', monospace; "
                        "font-size: 14px; font-weight: 500; background: transparent; }}"
                    )
                    table.setCellWidget(index, 5, _right_aligned_widget(value_label))
                    table.setCellWidget(
                        index,
                        6,
                        _centered_widget(_transaction_badge(transaction_type)),
                    )

            filter_button.clicked.connect(load_table)
            load_table()
            content.addWidget(table_card)
            return page

        def _create_account(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Nova conta financeira")
            wrapper = QVBoxLayout(dialog)
            wrapper.setContentsMargins(0, 0, 0, 0)
            form_frame, form = make_two_column_form()
            wrapper.addWidget(form_frame)
            name = QLineEdit()
            account_type = QComboBox()
            account_type.addItems(["checking", "cash", "payment", "asaas", "card", "investment"])
            opening_balance = QLineEdit("0,00")
            balance_date = QDateEdit()
            balance_date.setCalendarPopup(True)
            balance_date.setDate(QDate.currentDate())
            form.addWidget(_field_label("Nome"), 0, 0)
            form.addWidget(name, 1, 0)
            form.addWidget(_field_label("Tipo"), 0, 1)
            form.addWidget(account_type, 1, 1)
            form.addWidget(_field_label("Saldo inicial"), 2, 0)
            form.addWidget(opening_balance, 3, 0)
            form.addWidget(_field_label("Data do saldo"), 2, 1)
            form.addWidget(balance_date, 3, 1)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar conta")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            wrapper.addWidget(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    create_financial_account(
                        connection,
                        name=_required_text(name, "Nome"),
                        account_type=account_type.currentText(),
                        opening_balance_cents=parse_brl_to_cents(opening_balance.text()),
                        balance_date=_qdate_to_date(balance_date.date()),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except (ValueError, TypeError) as exc:
                QMessageBox.warning(self, "Conta nao criada", str(exc))
                return
            self._refresh_current_page()

        def _create_category(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Nova categoria")
            form = QFormLayout(dialog)
            name = QLineEdit()
            kind = QComboBox()
            kind.addItems(["revenue", "expense"])
            form.addRow("Nome", name)
            form.addRow("Tipo", kind)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    create_category(
                        connection,
                        name=_required_text(name, "Nome"),
                        kind=kind.currentText(),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Categoria nao criada", str(exc))
                return
            self._refresh_current_page()

        def _create_cost_center(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Novo centro de custo")
            form = QFormLayout(dialog)
            name = QLineEdit()
            description = QLineEdit()
            form.addRow("Nome", name)
            form.addRow("Descricao", description)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            with connect(settings.database_path) as connection:
                create_cost_center(
                    connection,
                    name=_required_text(name, "Nome"),
                    description=description.text().strip() or None,
                    actor_user_id=get_session_user_id(connection, self._session_id),
                )
            self._refresh_current_page()

        def _create_revenue(self) -> None:
            self._create_transaction(transaction_type="revenue")

        def _create_expense(self) -> None:
            self._create_transaction(transaction_type="expense")

        def _create_transaction(self, *, transaction_type: str) -> None:
            dialog = QDialog(self)
            title = "Nova receita" if transaction_type == "revenue" else "Nova despesa"
            dialog.setWindowTitle(title)
            wrapper = QVBoxLayout(dialog)
            wrapper.setContentsMargins(0, 0, 0, 0)
            form_frame, form = make_two_column_form()
            wrapper.addWidget(form_frame)
            account = QComboBox()
            category = QComboBox()
            cost_center = QComboBox()
            with connect(settings.database_path) as connection:
                _fill_combo(account, list_financial_accounts(connection), "name")
                _fill_combo(category, list_categories(connection, kind=transaction_type), "name")
                _fill_combo(cost_center, list_cost_centers(connection), "name", include_empty=True)
            description = QLineEdit()
            amount = QLineEdit("0,00")
            effective_date = QDateEdit()
            effective_date.setCalendarPopup(True)
            effective_date.setDate(QDate.currentDate())
            series_mode = QComboBox()
            series_mode.addItem("Unico", "single")
            series_mode.addItem("Parcelado mensal", "installment")
            series_mode.addItem("Recorrente mensal", "recurring")
            series_count = QLineEdit("1")
            suggestion_button = QPushButton("Sugerir categoria")
            suggestion_button.clicked.connect(
                lambda: self._apply_categorization_suggestion(
                    description=description,
                    transaction_type=transaction_type,
                    category=category,
                    cost_center=cost_center,
                )
            )
            form.addWidget(_field_label("Descricao"), 0, 0)
            form.addWidget(description, 1, 0)
            form.addWidget(_field_label("Valor"), 0, 1)
            form.addWidget(amount, 1, 1)
            form.addWidget(_field_label("Data"), 2, 0)
            form.addWidget(effective_date, 3, 0)
            form.addWidget(_field_label("Conta"), 2, 1)
            form.addWidget(account, 3, 1)
            form.addWidget(_field_label("Categoria"), 4, 0)
            form.addWidget(category, 5, 0)
            form.addWidget(_field_label("Modo"), 4, 1)
            form.addWidget(series_mode, 5, 1)
            form.addWidget(_field_label("Centro de custo"), 6, 0)
            form.addWidget(cost_center, 7, 0)
            form.addWidget(_field_label("Quantidade"), 6, 1)
            form.addWidget(series_count, 7, 1)
            form.addWidget(suggestion_button, 8, 0)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar lancamento")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            wrapper.addWidget(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    mode = str(series_mode.currentData())
                    occurrence_count = _positive_int(series_count, "Quantidade")
                    user_id = get_session_user_id(connection, self._session_id)
                    transaction_amount = parse_brl_to_cents(amount.text())
                    transaction_description = _required_text(description, "Descricao")
                    transaction_date = _qdate_to_date(effective_date.date())
                    if mode != "single":
                        record_transaction_series(
                            connection,
                            transaction_type=transaction_type,
                            account_id=_required_combo_id(account, "Conta"),
                            total_amount_cents=transaction_amount,
                            description=transaction_description,
                            first_effective_date=transaction_date,
                            actor_user_id=user_id,
                            occurrence_count=occurrence_count,
                            mode=mode,
                            category_id=_required_combo_id(category, "Categoria"),
                            cost_center_id=_optional_combo_id(cost_center),
                        )
                    elif transaction_type == "revenue":
                        record_revenue(
                            connection,
                            account_id=_required_combo_id(account, "Conta"),
                            amount_cents=transaction_amount,
                            description=transaction_description,
                            effective_date=transaction_date,
                            actor_user_id=user_id,
                            category_id=_required_combo_id(category, "Categoria"),
                            cost_center_id=_optional_combo_id(cost_center),
                        )
                    else:
                        record_expense(
                            connection,
                            account_id=_required_combo_id(account, "Conta"),
                            amount_cents=transaction_amount,
                            description=transaction_description,
                            effective_date=transaction_date,
                            actor_user_id=user_id,
                            category_id=_required_combo_id(category, "Categoria"),
                            cost_center_id=_optional_combo_id(cost_center),
                        )
            except (ValueError, TypeError) as exc:
                QMessageBox.warning(self, "Lancamento nao criado", str(exc))
                return
            self._refresh_current_page()

        def _create_transfer(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Transferencia entre contas")
            form = QFormLayout(dialog)
            origin = QComboBox()
            destination = QComboBox()
            with connect(settings.database_path) as connection:
                rows = list_financial_accounts(connection)
                _fill_combo(origin, rows, "name")
                _fill_combo(destination, rows, "name")
            description = QLineEdit()
            amount = QLineEdit("0,00")
            effective_date = QDateEdit()
            effective_date.setCalendarPopup(True)
            effective_date.setDate(QDate.currentDate())
            form.addRow("Origem", origin)
            form.addRow("Destino", destination)
            form.addRow("Descricao", description)
            form.addRow("Valor", amount)
            form.addRow("Data", effective_date)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    record_transfer(
                        connection,
                        origin_account_id=int(origin.currentData()),
                        destination_account_id=int(destination.currentData()),
                        amount_cents=parse_brl_to_cents(amount.text()),
                        description=_required_text(description, "Descricao"),
                        effective_date=_qdate_to_date(effective_date.date()),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except (ValueError, TypeError) as exc:
                QMessageBox.warning(self, "Transferencia nao criada", str(exc))
                return
            self._refresh_current_page()

        def _cancel_selected_transaction(self, table: Any) -> None:
            transaction_id = _selected_row_id_from_column(table, 1)
            if transaction_id is None:
                QMessageBox.warning(self, "Cancelamento nao realizado", "Selecione um lancamento.")
                return
            try:
                with connect(settings.database_path) as connection:
                    cancel_financial_transaction(
                        connection,
                        transaction_id=transaction_id,
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Cancelamento nao realizado", str(exc))
                return
            self._refresh_current_page()

        def _create_due_entry(self, entry_type: str) -> None:
            dialog = QDialog(self)
            title = "Nova conta a pagar" if entry_type == "payable" else "Nova conta a receber"
            dialog.setWindowTitle(title)
            wrapper = QVBoxLayout(dialog)
            wrapper.setContentsMargins(0, 0, 0, 0)
            form_frame, form = make_two_column_form()
            wrapper.addWidget(form_frame)
            category_kind = "expense" if entry_type == "payable" else "revenue"
            category = QComboBox()
            cost_center = QComboBox()
            with connect(settings.database_path) as connection:
                _fill_combo(category, list_categories(connection, kind=category_kind), "name")
                _fill_combo(cost_center, list_cost_centers(connection), "name", include_empty=True)
            counterparty = QLineEdit()
            description = QLineEdit()
            amount = QLineEdit("0,00")
            due_date = QDateEdit()
            due_date.setCalendarPopup(True)
            due_date.setDate(QDate.currentDate())
            notes = QLineEdit()
            series_mode = QComboBox()
            series_mode.addItem("Unico", "single")
            series_mode.addItem("Parcelado mensal", "installment")
            series_mode.addItem("Recorrente mensal", "recurring")
            series_count = QLineEdit("1")
            suggestion_button = QPushButton("Sugerir categoria")
            suggestion_button.clicked.connect(
                lambda: self._apply_categorization_suggestion(
                    description=description,
                    transaction_type=category_kind,
                    category=category,
                    cost_center=cost_center,
                )
            )
            form.addWidget(_field_label("Descricao"), 0, 0)
            form.addWidget(description, 1, 0)
            form.addWidget(_field_label("Valor"), 0, 1)
            form.addWidget(amount, 1, 1)
            form.addWidget(_field_label("Data de vencimento"), 2, 0)
            form.addWidget(due_date, 3, 0)
            form.addWidget(_field_label("Pessoa"), 2, 1)
            form.addWidget(counterparty, 3, 1)
            form.addWidget(_field_label("Categoria"), 4, 0)
            form.addWidget(category, 5, 0)
            form.addWidget(_field_label("Modo"), 4, 1)
            form.addWidget(series_mode, 5, 1)
            form.addWidget(_field_label("Centro de custo"), 6, 0)
            form.addWidget(cost_center, 7, 0)
            form.addWidget(_field_label("Quantidade"), 6, 1)
            form.addWidget(series_count, 7, 1)
            form.addWidget(_field_label("Observacoes"), 8, 0)
            form.addWidget(notes, 9, 0, 1, 2)
            form.addWidget(suggestion_button, 10, 0)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar lancamento")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            wrapper.addWidget(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    mode = str(series_mode.currentData())
                    occurrence_count = _positive_int(series_count, "Quantidade")
                    user_id = get_session_user_id(connection, self._session_id)
                    entry_amount = parse_brl_to_cents(amount.text())
                    entry_description = _required_text(description, "Descricao")
                    entry_counterparty = _required_text(counterparty, "Pessoa")
                    entry_due_date = _qdate_to_date(due_date.date())
                    if mode == "single":
                        create_payable_receivable_entry(
                            connection,
                            entry_type=entry_type,
                            counterparty=entry_counterparty,
                            description=entry_description,
                            amount_cents=entry_amount,
                            due_date=entry_due_date,
                            actor_user_id=user_id,
                            category_id=_optional_combo_id(category),
                            cost_center_id=_optional_combo_id(cost_center),
                            notes=notes.text().strip() or None,
                        )
                    else:
                        create_payable_receivable_series(
                            connection,
                            entry_type=entry_type,
                            counterparty=entry_counterparty,
                            description=entry_description,
                            total_amount_cents=entry_amount,
                            first_due_date=entry_due_date,
                            actor_user_id=user_id,
                            occurrence_count=occurrence_count,
                            mode=mode,
                            category_id=_optional_combo_id(category),
                            cost_center_id=_optional_combo_id(cost_center),
                            notes=notes.text().strip() or None,
                        )
            except (ValueError, TypeError) as exc:
                QMessageBox.warning(self, "Titulo nao criado", str(exc))
                return
            self._refresh_current_page()

        def _cancel_selected_due_entry(self, table: Any) -> None:
            entry_id = _selected_row_id_from_column(table, 1)
            if entry_id is None:
                QMessageBox.warning(self, "Cancelamento nao realizado", "Selecione um titulo.")
                return
            try:
                with connect(settings.database_path) as connection:
                    cancel_payable_receivable_entry(
                        connection,
                        entry_id=entry_id,
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Cancelamento nao realizado", str(exc))
                return
            self._refresh_current_page()

        def _settle_selected_due_entry(self, table: Any) -> None:
            row = table.currentRow()
            entry_id = _selected_row_id_from_column(table, 1)
            if row < 0 or entry_id is None:
                QMessageBox.warning(self, "Baixa nao realizada", "Selecione um titulo.")
                return
            open_amount_label = table.cellWidget(row, 5)
            open_amount = "0,00"
            if isinstance(open_amount_label, QWidget):
                label = open_amount_label.findChild(QLabel)
                if label is not None:
                    open_amount = label.text().replace("-", "").replace("+", "").strip()
            dialog = QDialog(self)
            dialog.setWindowTitle("Baixar titulo")
            form = QFormLayout(dialog)
            account = QComboBox()
            with connect(settings.database_path) as connection:
                _fill_combo(account, list_financial_accounts(connection), "name")
            amount = QLineEdit(open_amount.replace("R$ ", ""))
            settlement_date = QDateEdit()
            settlement_date.setCalendarPopup(True)
            settlement_date.setDate(QDate.currentDate())
            form.addRow("Conta", account)
            form.addRow("Valor da baixa", amount)
            form.addRow("Data", settlement_date)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    settle_payable_receivable_entry(
                        connection,
                        entry_id=entry_id,
                        account_id=int(account.currentData()),
                        amount_cents=parse_brl_to_cents(amount.text()),
                        settlement_date=_qdate_to_date(settlement_date.date()),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except (ValueError, TypeError) as exc:
                QMessageBox.warning(self, "Baixa nao realizada", str(exc))
                return
            self._refresh_current_page()

        def _audit_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Auditoria")
            heading.setObjectName("heading")
            content.addWidget(heading)
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Data", "Usuario", "Acao", "Entidade", "Resultado"])
            with connect(settings.database_path) as connection:
                rows = connection.execute(
                    """
                    SELECT created_at, user_id, action, entity, result
                    FROM audit_log
                    ORDER BY id DESC
                    LIMIT 100
                    """
                ).fetchall()
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                for column, value in enumerate(row):
                    item_text = "" if value is None else str(value)
                    table.setItem(index, column, QTableWidgetItem(item_text))
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            content.addWidget(table)
            return page

        def _backup_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Backups")
            heading.setObjectName("heading")
            content.addWidget(heading)
            content.addWidget(
                QLabel("Crie um backup criptografado do banco local antes de operacoes sensiveis.")
            )
            button = QPushButton("Criar backup manual")
            button.clicked.connect(self._create_backup)
            content.addWidget(button)
            restore_button = QPushButton("Restaurar backup")
            restore_button.clicked.connect(self._restore_backup)
            content.addWidget(restore_button)
            content.addStretch(1)
            return page

        def _imports_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Importacoes")
            heading.setObjectName("heading")
            content.addWidget(heading)
            content.addWidget(QLabel("Importe movimentacoes realizadas ou titulos previstos."))
            template_actions = QHBoxLayout()
            csv_button = QPushButton("Template movimentacoes CSV")
            csv_button.clicked.connect(lambda: self._export_import_template("csv"))
            template_actions.addWidget(csv_button)
            xlsx_button = QPushButton("Template movimentacoes XLSX")
            xlsx_button.clicked.connect(lambda: self._export_import_template("xlsx"))
            template_actions.addWidget(xlsx_button)
            content.addLayout(template_actions)
            due_template_actions = QHBoxLayout()
            due_csv_button = QPushButton("Template titulos CSV")
            due_csv_button.clicked.connect(lambda: self._export_due_entries_template("csv"))
            due_template_actions.addWidget(due_csv_button)
            due_xlsx_button = QPushButton("Template titulos XLSX")
            due_xlsx_button.clicked.connect(lambda: self._export_due_entries_template("xlsx"))
            due_template_actions.addWidget(due_xlsx_button)
            content.addLayout(due_template_actions)
            import_button = QPushButton("Importar movimentacoes")
            import_button.clicked.connect(self._import_financial_file)
            content.addWidget(import_button)
            mapped_button = QPushButton("Importar movimentacoes com mapeamento")
            mapped_button.clicked.connect(lambda: self._import_financial_file(use_mapping=True))
            content.addWidget(mapped_button)
            due_import_button = QPushButton("Importar titulos previstos")
            due_import_button.clicked.connect(self._import_due_entries_file)
            content.addWidget(due_import_button)
            due_mapped_button = QPushButton("Importar titulos com mapeamento")
            due_mapped_button.clicked.connect(
                lambda: self._import_due_entries_file(use_mapping=True)
            )
            content.addWidget(due_mapped_button)
            content.addStretch(1)
            return page

        def _asaas_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Asaas")
            heading.setObjectName("heading")
            content.addWidget(heading)
            status = "configurada" if settings.asaas_api_key else "nao configurada"
            content.addWidget(
                QLabel(f"Integracao leitura-only: {settings.asaas_env} | chave {status}")
            )
            sync_button = QPushButton("Sincronizar cobrancas")
            sync_button.clicked.connect(self._sync_asaas_payments)
            content.addWidget(sync_button)
            filters = QHBoxLayout()
            status_filter = QComboBox()
            status_filter.addItems(["Todos", "RECEIVED", "CONFIRMED", "PENDING", "OVERDUE"])
            if self._asaas_status_filter:
                status_filter.setCurrentText(self._asaas_status_filter)
            search_filter = QLineEdit()
            search_filter.setPlaceholderText("Buscar ID, cliente ou descricao")
            search_filter.setText(self._asaas_search_filter)
            start_filter = QDateEdit()
            start_filter.setCalendarPopup(True)
            start_filter.setDate(
                QDate(
                    self._asaas_start_filter.year,
                    self._asaas_start_filter.month,
                    self._asaas_start_filter.day,
                )
            )
            end_filter = QDateEdit()
            end_filter.setCalendarPopup(True)
            end_filter.setDate(
                QDate(
                    self._asaas_end_filter.year,
                    self._asaas_end_filter.month,
                    self._asaas_end_filter.day,
                )
            )
            filter_button = QPushButton("Filtrar")
            filter_button.clicked.connect(
                lambda: self._apply_asaas_filters(
                    status_filter,
                    search_filter,
                    start_filter,
                    end_filter,
                )
            )
            for widget in [
                QLabel("Status"),
                status_filter,
                QLabel("Texto"),
                search_filter,
                QLabel("Inicio"),
                start_filter,
                QLabel("Fim"),
                end_filter,
                filter_button,
            ]:
                filters.addWidget(widget)
            content.addLayout(filters)
            with connect(settings.database_path) as connection:
                payments = list_asaas_payments(
                    connection,
                    limit=25,
                    status=self._asaas_status_filter or None,
                    search=self._asaas_search_filter or None,
                )
                matches = suggest_asaas_matches(
                    connection,
                    start_date=self._asaas_start_filter,
                    end_date=self._asaas_end_filter,
                )
                reconciliations = list_asaas_reconciliations(
                    connection,
                    start_date=self._asaas_start_filter,
                    end_date=self._asaas_end_filter,
                )
            payments_table = QTableWidget()
            payments_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            payments_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            payments_table.setColumnCount(6)
            payments_table.setHorizontalHeaderLabels(
                ["ID Asaas", "Status", "Cliente", "Descricao", "Valor", "Recebimento"]
            )
            payments_table.setRowCount(len(payments))
            for index, payment in enumerate(payments):
                values = [
                    str(payment["asaas_id"]),
                    str(payment["status"]),
                    "" if payment["customer_name"] is None else str(payment["customer_name"]),
                    "" if payment["description"] is None else str(payment["description"]),
                    format_brl_cents(_dict_int(payment, "value_cents")),
                    "" if payment["payment_date"] is None else str(payment["payment_date"]),
                ]
                for column, value in enumerate(values):
                    payments_table.setItem(index, column, QTableWidgetItem(value))
            content.addWidget(QLabel("Cobranças sincronizadas"))
            content.addWidget(payments_table)
            matches_table = QTableWidget()
            matches_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            matches_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            matches_table.setColumnCount(7)
            matches_table.setHorizontalHeaderLabels(
                ["ID Asaas", "Lancamento", "Valor", "Data", "Confianca", "_tx", "_motivo"]
            )
            matches_table.setRowCount(len(matches))
            for index, match in enumerate(matches):
                values = [
                    str(match["asaas_id"]),
                    str(match["transaction_description"]),
                    format_brl_cents(_dict_int(match, "value_cents")),
                    str(match["payment_date"]),
                    f"{match['confidence']}%",
                    str(match["transaction_id"]),
                    str(match["reason"]),
                ]
                for column, value in enumerate(values):
                    matches_table.setItem(index, column, QTableWidgetItem(value))
            matches_table.setColumnHidden(5, True)
            matches_table.setColumnHidden(6, True)
            content.addWidget(QLabel("Sugestoes de conciliacao"))
            content.addWidget(matches_table)
            accept_button = QPushButton("Aceitar conciliacao selecionada")
            accept_button.clicked.connect(lambda: self._accept_selected_asaas_match(matches_table))
            content.addWidget(accept_button)
            reconciled_table = QTableWidget()
            reconciled_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            reconciled_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            reconciled_table.setColumnCount(6)
            reconciled_table.setHorizontalHeaderLabels(
                ["ID Asaas", "Lancamento", "Valor", "Data", "Confianca", "_id"]
            )
            reconciled_table.setRowCount(len(reconciliations))
            for index, reconciliation in enumerate(reconciliations):
                values = [
                    str(reconciliation["asaas_id"]),
                    str(reconciliation["transaction_description"]),
                    format_brl_cents(_dict_int(reconciliation, "value_cents")),
                    str(reconciliation["payment_date"]),
                    f"{reconciliation['confidence']}%",
                    str(reconciliation["id"]),
                ]
                for column, value in enumerate(values):
                    reconciled_table.setItem(index, column, QTableWidgetItem(value))
            reconciled_table.setColumnHidden(5, True)
            content.addWidget(QLabel("Conciliacoes aceitas"))
            content.addWidget(reconciled_table)
            cancel_reconciliation_button = QPushButton("Desconciliar selecionada")
            cancel_reconciliation_button.clicked.connect(
                lambda: self._cancel_selected_asaas_reconciliation(reconciled_table)
            )
            content.addWidget(cancel_reconciliation_button)
            return page

        def _sensitive_operations_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Aprovacoes sensiveis")
            heading.setObjectName("heading")
            content.addWidget(heading)
            content.addWidget(
                QLabel(
                    "Solicitacoes locais para operacoes futuras de alto risco. "
                    "Nenhuma chamada externa e executada nesta tela."
                )
            )
            actions = QHBoxLayout()
            create_button = QPushButton("Nova solicitacao")
            create_button.clicked.connect(self._create_sensitive_operation_dialog)
            actions.addWidget(create_button)
            status_filter = QComboBox()
            for label, value in [
                ("Todos status", None),
                ("Pendentes", "pending"),
                ("Aprovadas", "approved"),
                ("Rejeitadas", "rejected"),
                ("Canceladas", "canceled"),
                ("Executadas", "executed"),
            ]:
                status_filter.addItem(label, value)
            table = QTableWidget()
            filter_button = QPushButton("Filtrar")
            filter_button.clicked.connect(
                lambda: self._load_sensitive_operations_table(table, status_filter)
            )
            detail_button = QPushButton("Ver detalhe")
            detail_button.clicked.connect(lambda: self._show_sensitive_operation_detail(table))
            readiness_button = QPushButton("Exportar prontidao")
            readiness_button.clicked.connect(
                lambda: self._export_sensitive_operation_readiness(table)
            )
            evidence_button = QPushButton("Exportar evidencia")
            evidence_button.clicked.connect(
                lambda: self._export_sensitive_operation_execution_report(table)
            )
            package_button = QPushButton("Exportar pacote")
            package_button.clicked.connect(
                lambda: self._export_sensitive_operation_validation_package(table)
            )
            summary_button = QPushButton("Exportar resumo")
            summary_button.clicked.connect(
                lambda: self._export_sensitive_operation_review_summary(table)
            )
            execute_button = QPushButton("Executar Sandbox")
            execute_button.clicked.connect(
                lambda: self._execute_selected_sensitive_operation_sandbox(table)
            )
            approve_button = QPushButton("Aprovar")
            approve_button.clicked.connect(
                lambda: self._decide_selected_sensitive_operation(table, "approved")
            )
            reject_button = QPushButton("Rejeitar")
            reject_button.clicked.connect(
                lambda: self._decide_selected_sensitive_operation(table, "rejected")
            )
            cancel_button = QPushButton("Cancelar")
            cancel_button.clicked.connect(lambda: self._cancel_selected_sensitive_operation(table))
            for widget in [
                QLabel("Status"),
                status_filter,
                filter_button,
                detail_button,
                readiness_button,
                evidence_button,
                package_button,
                summary_button,
                execute_button,
                approve_button,
                reject_button,
                cancel_button,
            ]:
                actions.addWidget(widget)
            content.addLayout(actions)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setColumnCount(9)
            table.setHorizontalHeaderLabels(
                [
                    "ID",
                    "Status",
                    "Operacao",
                    "Titulo",
                    "Valor",
                    "Referencia",
                    "Solicitante",
                    "Aprov.",
                    "Rej.",
                ]
            )
            content.addWidget(table)
            self._load_sensitive_operations_table(table, status_filter)
            return page

        def _pdv_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("PDV e estoque")
            heading.setObjectName("heading")
            content.addWidget(heading)
            pdv_status = "configurado" if settings.pdv_database_url else "nao configurado"
            content.addWidget(QLabel(f"Integracao leitura-only com PDV: {pdv_status}"))
            actions = QHBoxLayout()
            sync_button = QPushButton("Sincronizar PDV")
            sync_button.clicked.connect(self._sync_pdv_snapshots)
            actions.addWidget(sync_button)
            account = QComboBox()
            category = QComboBox()
            cost_center = QComboBox()
            with connect(settings.database_path) as connection:
                accounts = list_financial_accounts(connection)
                categories = list_categories(connection, kind="revenue")
                cost_centers = list_cost_centers(connection)
                summary = get_pdv_stock_summary(connection)
                products = list_pdv_products(connection)
                sales = list_pdv_sales(connection)
            _fill_combo(account, accounts, "name")
            _fill_filter_combo(category, categories, "Sem categoria")
            _fill_filter_combo(cost_center, cost_centers, "Sem centro")
            import_button = QPushButton("Importar vendas pagas")
            import_button.clicked.connect(
                lambda: self._import_pdv_sales(account, category, cost_center)
            )
            for widget in [
                QLabel("Conta destino"),
                account,
                QLabel("Categoria"),
                category,
                QLabel("Centro"),
                cost_center,
                import_button,
            ]:
                actions.addWidget(widget)
            content.addLayout(actions)
            content.addWidget(
                QLabel(
                    "Produtos ativos: "
                    f"{summary['product_count']} | Valor do estoque: "
                    f"{format_brl_cents(summary['stock_value_cents'])}"
                )
            )
            products_table = QTableWidget()
            products_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            products_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            products_table.setColumnCount(6)
            products_table.setHorizontalHeaderLabels(
                ["ID PDV", "SKU", "Produto", "Categoria", "Estoque", "Valor estoque"]
            )
            products_table.setRowCount(len(products))
            for index, product in enumerate(products):
                values = [
                    str(product["pdv_id"]),
                    "" if product["sku"] is None else str(product["sku"]),
                    str(product["name"]),
                    "" if product["category_name"] is None else str(product["category_name"]),
                    str(product["stock_quantity"]),
                    format_brl_cents(_dict_int(product, "stock_value_cents")),
                ]
                for column, value in enumerate(values):
                    products_table.setItem(index, column, QTableWidgetItem(value))
            content.addWidget(QLabel("Snapshot de produtos"))
            content.addWidget(products_table)
            sales_table = QTableWidget()
            sales_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            sales_table.setColumnCount(6)
            sales_table.setHorizontalHeaderLabels(
                ["ID PDV", "Data", "Valor", "Forma", "Status", "Lancamento"]
            )
            sales_table.setRowCount(len(sales))
            for index, sale in enumerate(sales):
                values = [
                    str(sale["pdv_id"]),
                    str(sale["sold_at"]),
                    format_brl_cents(_dict_int(sale, "total_cents")),
                    "" if sale["payment_method"] is None else str(sale["payment_method"]),
                    str(sale["status"]),
                    ""
                    if sale["imported_transaction_id"] is None
                    else str(sale["imported_transaction_id"]),
                ]
                for column, value in enumerate(values):
                    sales_table.setItem(index, column, QTableWidgetItem(value))
            content.addWidget(QLabel("Vendas sincronizadas"))
            content.addWidget(sales_table)
            return page

        def _purchases_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Compras")
            heading.setObjectName("heading")
            content.addWidget(heading)
            actions = QHBoxLayout()
            supplier_button = QPushButton("Novo fornecedor")
            supplier_button.clicked.connect(self._create_supplier_dialog)
            order_button = QPushButton("Novo pedido")
            order_button.clicked.connect(self._create_purchase_order_dialog)
            advance_button = QPushButton("Avancar etapa")
            receive_button = QPushButton("Registrar recebimento")
            payable_button = QPushButton("Gerar conta a pagar")
            for button in [
                supplier_button,
                order_button,
                advance_button,
                receive_button,
                payable_button,
            ]:
                actions.addWidget(button)
            content.addLayout(actions)
            with connect(settings.database_path) as connection:
                suppliers = list_purchase_suppliers(connection)
                orders = list_purchase_orders(connection)
            suppliers_table = QTableWidget()
            suppliers_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            suppliers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            suppliers_table.setColumnCount(6)
            suppliers_table.setHorizontalHeaderLabels(
                ["ID", "Fornecedor", "Documento", "Contato", "Email", "Ativo"]
            )
            suppliers_table.setRowCount(len(suppliers))
            for index, supplier in enumerate(suppliers):
                values = [
                    str(supplier["id"]),
                    str(supplier["name"]),
                    "" if supplier["document"] is None else str(supplier["document"]),
                    "" if supplier["contact_name"] is None else str(supplier["contact_name"]),
                    "" if supplier["email"] is None else str(supplier["email"]),
                    "Sim" if supplier["is_active"] else "Nao",
                ]
                for column, value in enumerate(values):
                    suppliers_table.setItem(index, column, QTableWidgetItem(value))
            content.addWidget(QLabel("Fornecedores"))
            content.addWidget(suppliers_table)
            orders_table = QTableWidget()
            orders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            orders_table.setColumnCount(8)
            orders_table.setHorizontalHeaderLabels(
                [
                    "ID",
                    "Fornecedor",
                    "Descricao",
                    "Total",
                    "Recebido",
                    "Status",
                    "Previsto",
                    "Titulo",
                ]
            )
            orders_table.setRowCount(len(orders))
            for index, order in enumerate(orders):
                values = [
                    str(order["id"]),
                    str(order["supplier_name"]),
                    str(order["description"]),
                    format_brl_cents(_dict_int(order, "total_cents")),
                    format_brl_cents(_dict_int(order, "received_cents")),
                    str(order["status"]),
                    "" if order["expected_date"] is None else str(order["expected_date"]),
                    "" if order["payable_entry_id"] is None else str(order["payable_entry_id"]),
                ]
                for column, value in enumerate(values):
                    orders_table.setItem(index, column, QTableWidgetItem(value))
            advance_button.clicked.connect(lambda: self._advance_selected_purchase(orders_table))
            receive_button.clicked.connect(lambda: self._receive_selected_purchase(orders_table))
            payable_button.clicked.connect(
                lambda: self._generate_selected_purchase_payable(orders_table)
            )
            content.addWidget(QLabel("Pedidos de compra"))
            content.addWidget(orders_table)
            return page

        def _documents_page(self) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel("Documentos")
            heading.setObjectName("heading")
            content.addWidget(heading)
            google_status = get_google_sheets_status(settings)
            content.addWidget(QLabel(f"Google Sheets: {google_status.message}"))
            actions = QHBoxLayout()
            entity_type = QComboBox()
            for label, value in [
                ("Lancamento", "financial_transaction"),
                ("Titulo", "payable_receivable_entry"),
                ("Fornecedor", "supplier"),
                ("Compra", "purchase_order"),
            ]:
                entity_type.addItem(label, value)
            entity_id = QLineEdit()
            entity_id.setPlaceholderText("ID")
            attach_button = QPushButton("Anexar arquivo")
            attach_button.clicked.connect(lambda: self._attach_document(entity_type, entity_id))
            open_button = QPushButton("Abrir selecionado")
            for widget in [QLabel("Vinculo"), entity_type, entity_id, attach_button, open_button]:
                actions.addWidget(widget)
            content.addLayout(actions)
            with connect(settings.database_path) as connection:
                documents = list_documents(connection)
                sheet_imports = list_google_sheet_imports(connection)
            documents_table = QTableWidget()
            documents_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            documents_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            documents_table.setColumnCount(7)
            documents_table.setHorizontalHeaderLabels(
                ["ID", "Arquivo", "Caminho", "SHA-256", "Bytes", "Tipo", "Vinculos"]
            )
            documents_table.setRowCount(len(documents))
            for index, document in enumerate(documents):
                values = [
                    str(document["id"]),
                    str(document["original_name"]),
                    str(document["stored_path"]),
                    str(document["sha256"]),
                    str(document["size_bytes"]),
                    "" if document["mime_type"] is None else str(document["mime_type"]),
                    "" if document["links"] is None else str(document["links"]),
                ]
                for column, value in enumerate(values):
                    documents_table.setItem(index, column, QTableWidgetItem(value))
            open_button.clicked.connect(lambda: self._open_selected_document(documents_table))
            content.addWidget(QLabel("Arquivos anexados"))
            content.addWidget(documents_table)
            imports_table = QTableWidget()
            imports_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            imports_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            imports_table.setColumnCount(5)
            imports_table.setHorizontalHeaderLabels(["ID", "Planilha", "Aba", "Linhas", "Data"])
            imports_table.setRowCount(len(sheet_imports))
            for index, sheet_import in enumerate(sheet_imports):
                values = [
                    str(sheet_import["id"]),
                    str(sheet_import["spreadsheet_id"]),
                    str(sheet_import["sheet_name"]),
                    str(sheet_import["rows_count"]),
                    str(sheet_import["created_at"]),
                ]
                for column, value in enumerate(values):
                    imports_table.setItem(index, column, QTableWidgetItem(value))
            content.addWidget(QLabel("Historico Google Sheets"))
            content.addWidget(imports_table)
            return page

        def _placeholder_page(self, title: str, body: str) -> QWidget:
            page = QWidget()
            content = QVBoxLayout(page)
            heading = QLabel(title)
            heading.setObjectName("heading")
            content.addWidget(heading)
            content.addWidget(QLabel(body))
            content.addStretch(1)
            return page

        def _create_backup(self) -> None:
            try:
                with connect(settings.database_path) as connection:
                    user_id = get_session_user_id(connection, self._session_id)
                    path = create_encrypted_backup(
                        connection,
                        settings=settings,
                        actor_user_id=user_id,
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Backup nao configurado", str(exc))
                return
            QMessageBox.information(self, "Backup criado", f"Arquivo gerado em:\n{path}")

        def _restore_backup(self) -> None:
            backup_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar backup",
                str(settings.paths.backups_dir),
                "Backups criptografados (*.fernet)",
            )
            if not backup_path:
                return
            first_answer = QMessageBox.question(
                self,
                "Confirmar restauracao",
                "A restauracao substitui o banco atual. Deseja continuar?",
            )
            if first_answer != QMessageBox.StandardButton.Yes:
                return
            second_answer = QMessageBox.question(
                self,
                "Confirmacao final",
                "Um backup preventivo sera criado antes da restauracao. Confirmar agora?",
            )
            if second_answer != QMessageBox.StandardButton.Yes:
                return
            try:
                preventive_path = restore_encrypted_backup(
                    backup_path=Path(backup_path),
                    settings=settings,
                )
            except (FileNotFoundError, ValueError) as exc:
                QMessageBox.warning(self, "Restauracao falhou", str(exc))
                return
            QMessageBox.information(
                self,
                "Backup restaurado",
                f"Restauracao concluida.\nBackup preventivo:\n{preventive_path}",
            )

        def _export_import_template(self, file_type: str) -> None:
            default_name = f"template-importacao-financeira.{file_type}"
            file_filter = "CSV (*.csv)" if file_type == "csv" else "Planilhas Excel (*.xlsx)"
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar template",
                str(settings.paths.documents_dir / "imports" / default_name),
                file_filter,
            )
            if not output_path:
                return
            if file_type == "csv":
                created_path = export_import_template_csv(Path(output_path))
            else:
                created_path = export_import_template_xlsx(Path(output_path))
            QMessageBox.information(self, "Template gerado", f"Arquivo gerado em:\n{created_path}")

        def _export_due_entries_template(self, file_type: str) -> None:
            default_name = f"template-titulos-previstos.{file_type}"
            file_filter = "CSV (*.csv)" if file_type == "csv" else "Planilhas Excel (*.xlsx)"
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar template",
                str(settings.paths.documents_dir / "imports" / default_name),
                file_filter,
            )
            if not output_path:
                return
            if file_type == "csv":
                created_path = export_due_entries_template_csv(Path(output_path))
            else:
                created_path = export_due_entries_template_xlsx(Path(output_path))
            QMessageBox.information(self, "Template gerado", f"Arquivo gerado em:\n{created_path}")

        def _import_financial_file(self, *, use_mapping: bool = False) -> None:
            source_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar arquivo de importacao",
                str(settings.paths.documents_dir),
                "Planilhas e CSV (*.xlsx *.csv)",
            )
            if not source_path:
                return
            import_path = Path(source_path)
            column_mapping = None
            if use_mapping:
                column_mapping = self._request_import_mapping(
                    import_path,
                    required_fields=REQUIRED_HEADERS,
                    optional_fields=OPTIONAL_HEADERS,
                )
                if column_mapping is None:
                    return
            try:
                with connect(settings.database_path) as connection:
                    preview = preview_financial_import(
                        connection,
                        source_path=import_path,
                        column_mapping=column_mapping,
                    )
                    if (
                        not use_mapping
                        and preview.errors
                        and preview.errors[0].line_number == 1
                        and "Colunas obrigatorias ausentes" in preview.errors[0].message
                    ):
                        answer = QMessageBox.question(
                            self,
                            "Mapear colunas",
                            "O arquivo nao segue o template. Deseja mapear as colunas agora?",
                        )
                        if answer == QMessageBox.StandardButton.Yes:
                            column_mapping = self._request_import_mapping(
                                import_path,
                                required_fields=REQUIRED_HEADERS,
                                optional_fields=OPTIONAL_HEADERS,
                            )
                            if column_mapping is None:
                                return
                            preview = preview_financial_import(
                                connection,
                                source_path=import_path,
                                column_mapping=column_mapping,
                            )
                    if not self._show_import_preview(preview):
                        return
                    if preview.errors:
                        return
                    result = import_financial_transactions(
                        connection,
                        source_path=import_path,
                        actor_user_id=get_session_user_id(connection, self._session_id),
                        column_mapping=column_mapping,
                    )
            except (FileNotFoundError, ValueError) as exc:
                QMessageBox.warning(self, "Importacao falhou", str(exc))
                return
            QMessageBox.information(
                self,
                "Importacao concluida",
                (
                    f"Registros importados: {result.imported_count}\n"
                    f"Duplicatas ignoradas: {result.skipped_duplicates}"
                ),
            )
            self._refresh_current_page()

        def _import_due_entries_file(self, *, use_mapping: bool = False) -> None:
            source_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar arquivo de titulos",
                str(settings.paths.documents_dir),
                "Planilhas e CSV (*.xlsx *.csv)",
            )
            if not source_path:
                return
            import_path = Path(source_path)
            column_mapping = None
            if use_mapping:
                column_mapping = self._request_import_mapping(
                    import_path,
                    required_fields=DUE_REQUIRED_HEADERS,
                    optional_fields=DUE_OPTIONAL_HEADERS,
                )
                if column_mapping is None:
                    return
            try:
                with connect(settings.database_path) as connection:
                    preview = preview_due_entries_import(
                        connection,
                        source_path=import_path,
                        column_mapping=column_mapping,
                    )
                    if (
                        not use_mapping
                        and preview.errors
                        and preview.errors[0].line_number == 1
                        and "Colunas obrigatorias ausentes" in preview.errors[0].message
                    ):
                        answer = QMessageBox.question(
                            self,
                            "Mapear colunas",
                            "O arquivo nao segue o template. Deseja mapear as colunas agora?",
                        )
                        if answer == QMessageBox.StandardButton.Yes:
                            column_mapping = self._request_import_mapping(
                                import_path,
                                required_fields=DUE_REQUIRED_HEADERS,
                                optional_fields=DUE_OPTIONAL_HEADERS,
                            )
                            if column_mapping is None:
                                return
                            preview = preview_due_entries_import(
                                connection,
                                source_path=import_path,
                                column_mapping=column_mapping,
                            )
                    if not self._show_import_preview(preview):
                        return
                    if preview.errors:
                        return
                    result = import_due_entries(
                        connection,
                        source_path=import_path,
                        actor_user_id=get_session_user_id(connection, self._session_id),
                        column_mapping=column_mapping,
                    )
            except (FileNotFoundError, ValueError) as exc:
                QMessageBox.warning(self, "Importacao falhou", str(exc))
                return
            QMessageBox.information(
                self,
                "Importacao concluida",
                (
                    f"Titulos importados: {result.imported_count}\n"
                    f"Duplicatas ignoradas: {result.skipped_duplicates}"
                ),
            )
            self._refresh_current_page()

        def _request_import_mapping(
            self,
            source_path: Path,
            *,
            required_fields: list[str],
            optional_fields: list[str],
        ) -> dict[str, str] | None:
            try:
                source_headers = read_import_headers(source_path)
            except ValueError as exc:
                QMessageBox.warning(self, "Mapeamento indisponivel", str(exc))
                return None
            fields = [*required_fields, *optional_fields]
            dialog = QDialog(self)
            dialog.setWindowTitle("Mapear colunas")
            form = QFormLayout(dialog)
            combos: dict[str, QComboBox] = {}
            for field in fields:
                combo = QComboBox()
                combo.addItem("")
                for header in source_headers:
                    combo.addItem(header)
                if field in source_headers:
                    combo.setCurrentText(field)
                combos[field] = combo
                label = f"{field} *" if field in required_fields else field
                form.addRow(label, combo)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            mapping = {field: combo.currentText().strip() for field, combo in combos.items()}
            missing = [field for field in required_fields if not mapping[field]]
            if missing:
                QMessageBox.warning(
                    self,
                    "Mapeamento incompleto",
                    f"Campos obrigatorios sem coluna: {', '.join(missing)}",
                )
                return None
            return {field: header for field, header in mapping.items() if header}

        def _show_import_preview(self, preview: ImportPreview | DueEntryImportPreview) -> bool:
            dialog = QDialog(self)
            dialog.setWindowTitle("Pre-visualizar importacao")
            dialog.setMinimumSize(760, 420)
            layout = QVBoxLayout(dialog)
            layout.addWidget(
                QLabel(
                    f"Linhas validas: {len(preview.valid_rows)} | "
                    f"Erros: {len(preview.errors)} | "
                    f"Duplicatas ignoradas: {preview.duplicate_count}"
                )
            )
            table = QTableWidget()
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            if preview.errors:
                table.setColumnCount(2)
                table.setHorizontalHeaderLabels(["Linha", "Erro"])
                table.setRowCount(len(preview.errors))
                for index, error in enumerate(preview.errors):
                    table.setItem(index, 0, QTableWidgetItem(str(error.line_number)))
                    table.setItem(index, 1, QTableWidgetItem(error.message))
            elif isinstance(preview, ImportPreview):
                preview_rows = preview.valid_rows[:50]
                table.setColumnCount(7)
                table.setHorizontalHeaderLabels(
                    ["Linha", "Tipo", "Data", "Descricao", "Valor", "Categoria", "Origem"]
                )
                table.setRowCount(len(preview_rows))
                for index, row in enumerate(preview_rows):
                    values = [
                        str(row.line_number),
                        "Receita" if row.transaction_type == "revenue" else "Despesa",
                        row.effective_date.isoformat(),
                        row.description,
                        format_brl_cents(row.amount_cents),
                        row.category_name,
                        row.categorization_source,
                    ]
                    for column, value in enumerate(values):
                        table.setItem(index, column, QTableWidgetItem(value))
            else:
                due_preview_rows = preview.valid_rows[:50]
                table.setColumnCount(8)
                table.setHorizontalHeaderLabels(
                    [
                        "Linha",
                        "Tipo",
                        "Vencimento",
                        "Contraparte",
                        "Descricao",
                        "Valor",
                        "Categoria",
                        "Origem",
                    ]
                )
                table.setRowCount(len(due_preview_rows))
                for index, due_row in enumerate(due_preview_rows):
                    values = [
                        str(due_row.line_number),
                        "A pagar" if due_row.entry_type == "payable" else "A receber",
                        due_row.due_date.isoformat(),
                        due_row.counterparty,
                        due_row.description,
                        format_brl_cents(due_row.amount_cents),
                        due_row.category_name,
                        due_row.categorization_source,
                    ]
                    for column, value in enumerate(values):
                        table.setItem(index, column, QTableWidgetItem(value))
            layout.addWidget(table)
            if preview.valid_rows:
                categorization_button = QPushButton("Exportar categorizacao CSV")
                categorization_button.clicked.connect(
                    lambda: self._export_import_categorization_report(preview)
                )
                layout.addWidget(categorization_button)
            if preview.errors:
                export_button = QPushButton("Exportar erros CSV")
                export_button.clicked.connect(lambda: self._export_import_errors(preview))
                layout.addWidget(export_button)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Save).setText(
                "Importar" if not preview.errors else "Fechar"
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            return dialog.exec() == QDialog.DialogCode.Accepted

        def _export_import_errors(self, preview: ImportPreview | DueEntryImportPreview) -> None:
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar relatorio de erros",
                str(settings.paths.documents_dir / "imports" / "erros-importacao.csv"),
                "CSV (*.csv)",
            )
            if not output_path:
                return
            created_path = export_import_error_report_csv(Path(output_path), preview)
            QMessageBox.information(
                self,
                "Relatorio gerado",
                f"Arquivo gerado em:\n{created_path}",
            )

        def _export_import_categorization_report(
            self,
            preview: ImportPreview | DueEntryImportPreview,
        ) -> None:
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar relatorio de categorizacao",
                str(settings.paths.documents_dir / "imports" / "categorizacao-importacao.csv"),
                "CSV (*.csv)",
            )
            if not output_path:
                return
            created_path = export_import_categorization_report_csv(Path(output_path), preview)
            QMessageBox.information(
                self,
                "Relatorio gerado",
                f"Arquivo gerado em:\n{created_path}",
            )

        def _apply_dashboard_filters(
            self,
            start_filter: QDateEdit,
            end_filter: QDateEdit,
        ) -> None:
            start_date = _qdate_to_date(start_filter.date())
            end_date = _qdate_to_date(end_filter.date())
            if start_date > end_date:
                QMessageBox.warning(self, "Dashboard", "Data inicial maior que a final.")
                return
            self._selected_dashboard_id = None
            self._dashboard_start_filter = start_date
            self._dashboard_end_filter = end_date
            self._refresh_current_page()

        def _apply_custom_dashboard(self, profile_filter: QComboBox) -> None:
            dashboard_id = profile_filter.currentData()
            self._selected_dashboard_id = None if dashboard_id is None else int(dashboard_id)
            with connect(settings.database_path) as connection:
                selected_dashboard = (
                    get_custom_dashboard(connection, self._selected_dashboard_id)
                    if self._selected_dashboard_id is not None
                    else None
                )
            if selected_dashboard is not None and selected_dashboard.period_preset != "custom":
                self._dashboard_start_filter, self._dashboard_end_filter = _dashboard_period(
                    selected_dashboard.period_preset,
                    today=date.today(),
                    custom_start=self._dashboard_start_filter,
                    custom_end=self._dashboard_end_filter,
                )
            self._refresh_current_page()

        def _save_custom_dashboard_dialog(self) -> None:
            with connect(settings.database_path) as connection:
                current_dashboard = (
                    get_custom_dashboard(connection, self._selected_dashboard_id)
                    if self._selected_dashboard_id is not None
                    else None
                )
            dialog = QDialog(self)
            dialog.setWindowTitle("Salvar painel personalizado")
            form = QFormLayout(dialog)
            name = QLineEdit(current_dashboard.name if current_dashboard is not None else "")
            period = QComboBox()
            period_options = [
                ("Mes atual", "current_month"),
                ("Ultimos 30 dias", "last_30_days"),
                ("Ano atual", "current_year"),
                ("Periodo manual", "custom"),
            ]
            for label, value in period_options:
                period.addItem(label, value)
                if current_dashboard is not None and current_dashboard.period_preset == value:
                    period.setCurrentIndex(period.count() - 1)
            item_limit = QSpinBox()
            item_limit.setRange(1, 20)
            item_limit.setValue(
                current_dashboard.item_limit if current_dashboard is not None else 8
            )
            alert_days = QSpinBox()
            alert_days.setRange(0, 90)
            alert_days.setValue(
                current_dashboard.alert_days if current_dashboard is not None else 7
            )
            show_revenue_categories = QCheckBox("Receitas por categoria")
            show_expense_categories = QCheckBox("Despesas por categoria")
            show_cost_centers = QCheckBox("Centros de custo")
            show_due_alerts = QCheckBox("Alertas de vencimento")
            section_checks = [
                show_revenue_categories,
                show_expense_categories,
                show_cost_centers,
                show_due_alerts,
            ]
            for checkbox in section_checks:
                checkbox.setChecked(True)
            if current_dashboard is not None:
                show_revenue_categories.setChecked(current_dashboard.show_revenue_categories)
                show_expense_categories.setChecked(current_dashboard.show_expense_categories)
                show_cost_centers.setChecked(current_dashboard.show_cost_centers)
                show_due_alerts.setChecked(current_dashboard.show_due_alerts)
            for label, widget in [
                ("Nome", name),
                ("Periodo", period),
                ("Linhas por secao", item_limit),
                ("Dias de alerta", alert_days),
            ]:
                form.addRow(label, widget)
            for checkbox in section_checks:
                form.addRow(checkbox)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    dashboard_id = upsert_custom_dashboard(
                        connection,
                        dashboard_id=self._selected_dashboard_id,
                        name=name.text(),
                        period_preset=str(period.currentData()),
                        item_limit=item_limit.value(),
                        alert_days=alert_days.value(),
                        show_revenue_categories=show_revenue_categories.isChecked(),
                        show_expense_categories=show_expense_categories.isChecked(),
                        show_cost_centers=show_cost_centers.isChecked(),
                        show_due_alerts=show_due_alerts.isChecked(),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
                    connection.commit()
            except (ValueError, RuntimeError) as exc:
                QMessageBox.warning(self, "Dashboard", str(exc))
                return
            self._selected_dashboard_id = dashboard_id
            self._refresh_current_page()

        def _apply_planning_filters(self, year_filter: QLineEdit, month_filter: QComboBox) -> None:
            try:
                year = _positive_int(year_filter, "Ano")
                if year < 2000 or year > 2100:
                    raise ValueError("Ano precisa estar entre 2000 e 2100")
                month = _required_combo_id(month_filter, "Mes")
            except ValueError as exc:
                QMessageBox.warning(self, "Planejamento", str(exc))
                return
            self._planning_year = year
            self._planning_month = month
            self._refresh_current_page()

        def _create_budget_dialog(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Novo orcamento")
            form = QFormLayout(dialog)
            year = QLineEdit(str(self._planning_year))
            month = QComboBox()
            for value in range(1, 13):
                month.addItem(f"{value:02d}", value)
            month.setCurrentIndex(self._planning_month - 1)
            category = QComboBox()
            cost_center = QComboBox()
            amount = QLineEdit()
            notes = QLineEdit()
            with connect(settings.database_path) as connection:
                _fill_combo(category, list_categories(connection), "name")
                _fill_filter_combo(cost_center, list_cost_centers(connection), "Sem centro")
            form.addRow("Ano", year)
            form.addRow("Mes", month)
            form.addRow("Categoria", category)
            form.addRow("Centro", cost_center)
            form.addRow("Valor", amount)
            form.addRow("Observacoes", notes)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    upsert_budget(
                        connection,
                        year=_positive_int(year, "Ano"),
                        month=_required_combo_id(month, "Mes"),
                        category_id=_required_combo_id(category, "Categoria"),
                        cost_center_id=_optional_combo_id(cost_center),
                        amount_cents=parse_brl_to_cents(amount.text()),
                        notes=notes.text(),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Orcamento invalido", str(exc))
                return
            self._refresh_current_page()

        def _create_annual_budget_dialog(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Orcamento anual")
            form = QFormLayout(dialog)
            year = QLineEdit(str(self._planning_year))
            category = QComboBox()
            cost_center = QComboBox()
            total = QLineEdit()
            notes = QLineEdit()
            distribution_mode = QComboBox()
            distribution_mode.addItem("Linear", "linear")
            distribution_mode.addItem("Sazonal por pesos", "seasonal")
            weight_inputs = [QLineEdit("1") for _ in range(12)]
            weights_widget = QWidget()
            weights_layout = QVBoxLayout(weights_widget)
            month_labels = [
                "Jan",
                "Fev",
                "Mar",
                "Abr",
                "Mai",
                "Jun",
                "Jul",
                "Ago",
                "Set",
                "Out",
                "Nov",
                "Dez",
            ]
            for row_start in range(0, 12, 4):
                row_layout = QHBoxLayout()
                for index in range(row_start, row_start + 4):
                    row_layout.addWidget(QLabel(month_labels[index]))
                    weight_inputs[index].setFixedWidth(48)
                    row_layout.addWidget(weight_inputs[index])
                weights_layout.addLayout(row_layout)
            with connect(settings.database_path) as connection:
                _fill_combo(category, list_categories(connection), "name")
                _fill_filter_combo(cost_center, list_cost_centers(connection), "Sem centro")
            form.addRow("Ano", year)
            form.addRow("Categoria", category)
            form.addRow("Centro", cost_center)
            form.addRow("Total anual", total)
            form.addRow("Distribuicao", distribution_mode)
            form.addRow("Pesos mensais", weights_widget)
            form.addRow("Observacoes", notes)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    budget_ids = distribute_annual_budget(
                        connection,
                        year=_positive_int(year, "Ano"),
                        category_id=_required_combo_id(category, "Categoria"),
                        cost_center_id=_optional_combo_id(cost_center),
                        total_amount_cents=parse_brl_to_cents(total.text()),
                        monthly_weights=_monthly_weights_from_inputs(
                            weight_inputs,
                            enabled=distribution_mode.currentData() == "seasonal",
                        ),
                        notes=notes.text(),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Orcamento anual invalido", str(exc))
                return
            QMessageBox.information(
                self,
                "Orcamento anual criado",
                f"{len(budget_ids)} meses foram atualizados para o ano informado.",
            )
            self._refresh_current_page()

        def _create_categorization_rule_dialog(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Nova regra de categorizacao")
            form = QFormLayout(dialog)
            keyword = QLineEdit()
            transaction_type = QComboBox()
            transaction_type.addItem("Todos", None)
            transaction_type.addItem("Receita", "revenue")
            transaction_type.addItem("Despesa", "expense")
            category = QComboBox()
            cost_center = QComboBox()
            priority = QLineEdit("100")
            with connect(settings.database_path) as connection:
                _fill_combo(category, list_categories(connection), "name")
                _fill_filter_combo(cost_center, list_cost_centers(connection), "Sem centro")
            form.addRow("Palavra-chave", keyword)
            form.addRow("Tipo", transaction_type)
            form.addRow("Categoria", category)
            form.addRow("Centro", cost_center)
            form.addRow("Prioridade", priority)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    create_categorization_rule(
                        connection,
                        keyword=_required_text(keyword, "Palavra-chave"),
                        transaction_type=_optional_combo_text(transaction_type),
                        category_id=_required_combo_id(category, "Categoria"),
                        cost_center_id=_optional_combo_id(cost_center),
                        priority=_positive_int(priority, "Prioridade"),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Regra invalida", str(exc))
                return
            self._refresh_current_page()

        def _apply_categorization_suggestion(
            self,
            *,
            description: QLineEdit,
            transaction_type: str,
            category: QComboBox,
            cost_center: QComboBox,
        ) -> None:
            description_text = description.text().strip()
            if not description_text:
                QMessageBox.warning(
                    self,
                    "Sugestao de categoria",
                    "Preencha a descricao antes de sugerir uma categoria.",
                )
                return
            with connect(settings.database_path) as connection:
                suggestion = suggest_category_for_description(
                    connection,
                    description=description_text,
                    transaction_type=transaction_type,
                )
            if suggestion is None:
                QMessageBox.information(
                    self,
                    "Sugestao de categoria",
                    "Nenhuma regra local encontrou correspondencia.",
                )
                return
            _select_combo_data(category, suggestion.category_id)
            if suggestion.cost_center_id is not None:
                _select_combo_data(cost_center, suggestion.cost_center_id)
            QMessageBox.information(
                self,
                "Sugestao aplicada",
                f"Regra '{suggestion.keyword}' sugeriu {suggestion.category_name}.",
            )

        class SyncAsaasWorker(QObject):
            finished_sync = Signal(object)
            error_sync = Signal(str)

            def __init__(self, session_id, asaas_start, asaas_end):
                super().__init__()
                self.session_id = session_id
                self.asaas_start = asaas_start
                self.asaas_end = asaas_end

            def run(self):
                try:
                    with connect(settings.database_path) as connection:
                        result = sync_asaas_payments(
                            connection,
                            settings=settings,
                            actor_user_id=get_session_user_id(connection, self.session_id),
                            due_date_start=self.asaas_start,
                            due_date_end=self.asaas_end,
                        )
                        self.finished_sync.emit(result)
                except Exception as exc:
                    self.error_sync.emit(str(exc))

        def _sync_asaas_payments(self) -> None:
            self.setEnabled(False)
            
            self._asaas_thread = QThread()
            self._asaas_worker = MainWindow.SyncAsaasWorker(
                self._session_id, self._asaas_start_filter, self._asaas_end_filter
            )
            self._asaas_worker.moveToThread(self._asaas_thread)

            def on_finished(result):
                self.setEnabled(True)
                QMessageBox.information(
                    self,
                    "Sincronizacao concluida",
                    (
                        f"Cobrancas lidas: {result.fetched_count}\n"
                        f"Snapshots atualizados: {result.stored_count}"
                    ),
                )
                self._refresh_current_page()
                self._asaas_thread.quit()
                self._asaas_thread.wait()

            def on_error(msg):
                self.setEnabled(True)
                QMessageBox.warning(self, "Asaas indisponivel", msg)
                self._asaas_thread.quit()
                self._asaas_thread.wait()

            self._asaas_thread.started.connect(self._asaas_worker.run)
            self._asaas_worker.finished_sync.connect(on_finished)
            self._asaas_worker.error_sync.connect(on_error)
            
            self._asaas_thread.finished.connect(self._asaas_thread.deleteLater)
            self._asaas_worker.finished_sync.connect(self._asaas_worker.deleteLater)
            self._asaas_worker.error_sync.connect(self._asaas_worker.deleteLater)

            self._asaas_thread.start()

        class SyncPdvWorker(QObject):
            finished_sync = Signal(object)
            error_sync = Signal(str)

            def __init__(self, session_id):
                super().__init__()
                self.session_id = session_id

            def run(self):
                try:
                    with connect(settings.database_path) as connection:
                        result = sync_pdv_snapshots(
                            connection,
                            settings=settings,
                            actor_user_id=get_session_user_id(connection, self.session_id),
                        )
                        self.finished_sync.emit(result)
                except Exception as exc:
                    self.error_sync.emit(str(exc))

        def _sync_pdv_snapshots(self) -> None:
            self.setEnabled(False)
            
            self._pdv_thread = QThread()
            self._pdv_worker = MainWindow.SyncPdvWorker(self._session_id)
            self._pdv_worker.moveToThread(self._pdv_thread)

            def on_finished(result):
                self.setEnabled(True)
                QMessageBox.information(
                    self,
                    "Sincronizacao concluida",
                    (
                        f"Categorias: {result.categories_count}\n"
                        f"Produtos: {result.products_count}\n"
                        f"Vendas: {result.sales_count}"
                    ),
                )
                self._refresh_current_page()
                self._pdv_thread.quit()
                self._pdv_thread.wait()

            def on_error(msg):
                self.setEnabled(True)
                QMessageBox.warning(self, "PDV indisponivel", msg)
                self._pdv_thread.quit()
                self._pdv_thread.wait()

            self._pdv_thread.started.connect(self._pdv_worker.run)
            self._pdv_worker.finished_sync.connect(on_finished)
            self._pdv_worker.error_sync.connect(on_error)
            
            self._pdv_thread.finished.connect(self._pdv_thread.deleteLater)
            self._pdv_worker.finished_sync.connect(self._pdv_worker.deleteLater)
            self._pdv_worker.error_sync.connect(self._pdv_worker.deleteLater)

            self._pdv_thread.start()

        def _import_pdv_sales(
            self,
            account: QComboBox,
            category: QComboBox,
            cost_center: QComboBox,
        ) -> None:
            try:
                with connect(settings.database_path) as connection:
                    result = import_pdv_sales_as_revenue(
                        connection,
                        account_id=_required_combo_id(account, "Conta destino"),
                        category_id=_optional_combo_id(category),
                        cost_center_id=_optional_combo_id(cost_center),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Importacao PDV", str(exc))
                return
            QMessageBox.information(
                self,
                "Importacao concluida",
                (
                    f"Vendas importadas: {result.imported_count}\n"
                    f"Vendas ignoradas: {result.skipped_count}"
                ),
            )
            self._refresh_current_page()

        def _create_supplier_dialog(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Novo fornecedor")
            form = QFormLayout(dialog)
            name = QLineEdit()
            document = QLineEdit()
            contact = QLineEdit()
            email = QLineEdit()
            phone = QLineEdit()
            notes = QLineEdit()
            form.addRow("Nome", name)
            form.addRow("Documento", document)
            form.addRow("Contato", contact)
            form.addRow("Email", email)
            form.addRow("Telefone", phone)
            form.addRow("Observacoes", notes)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    create_supplier(
                        connection,
                        name=name.text(),
                        document=document.text(),
                        contact_name=contact.text(),
                        email=email.text(),
                        phone=phone.text(),
                        notes=notes.text(),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Fornecedor invalido", str(exc))
                return
            self._refresh_current_page()

        def _create_purchase_order_dialog(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Novo pedido de compra")
            form = QFormLayout(dialog)
            supplier = QComboBox()
            description = QLineEdit()
            total = QLineEdit()
            expected_date = QDateEdit()
            expected_date.setCalendarPopup(True)
            expected_date.setDate(QDate.currentDate())
            notes = QLineEdit()
            with connect(settings.database_path) as connection:
                _fill_combo(supplier, list_purchase_suppliers(connection), "name")
            form.addRow("Fornecedor", supplier)
            form.addRow("Descricao", description)
            form.addRow("Total", total)
            form.addRow("Data prevista", expected_date)
            form.addRow("Observacoes", notes)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    create_purchase_order(
                        connection,
                        supplier_id=_required_combo_id(supplier, "Fornecedor"),
                        description=description.text(),
                        total_cents=parse_brl_to_cents(total.text()),
                        expected_date=_qdate_to_date(expected_date.date()),
                        notes=notes.text(),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Pedido invalido", str(exc))
                return
            self._refresh_current_page()

        def _advance_selected_purchase(self, table: QTableWidget) -> None:
            order_id = _selected_table_id(table, "pedido de compra")
            if order_id is None:
                QMessageBox.warning(self, "Compras", "Selecione um pedido de compra.")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Avancar etapa da compra")
            form = QFormLayout(dialog)
            status = QComboBox()
            for label, value in [
                ("Cotacao", "quoted"),
                ("Aprovado", "approved"),
                ("Pedido enviado", "ordered"),
                ("Recebido conferido", "checked"),
                ("Entrada no estoque", "stock_entered"),
                ("Encerrado", "closed"),
                ("Cancelado", "canceled"),
            ]:
                status.addItem(label, value)
            form.addRow("Proxima etapa", status)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    advance_purchase_order(
                        connection,
                        purchase_order_id=order_id,
                        next_status=str(status.currentData()),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Etapa invalida", str(exc))
                return
            self._refresh_current_page()

        def _receive_selected_purchase(self, table: QTableWidget) -> None:
            order_id = _selected_table_id(table, "pedido de compra")
            if order_id is None:
                QMessageBox.warning(self, "Compras", "Selecione um pedido de compra.")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Registrar recebimento")
            form = QFormLayout(dialog)
            amount = QLineEdit()
            received_date = QDateEdit()
            received_date.setCalendarPopup(True)
            received_date.setDate(QDate.currentDate())
            notes = QLineEdit()
            form.addRow("Valor recebido", amount)
            form.addRow("Data", received_date)
            form.addRow("Observacoes", notes)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    receive_purchase_order(
                        connection,
                        purchase_order_id=order_id,
                        amount_cents=parse_brl_to_cents(amount.text()),
                        received_date=_qdate_to_date(received_date.date()),
                        notes=notes.text(),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Recebimento invalido", str(exc))
                return
            self._refresh_current_page()

        def _generate_selected_purchase_payable(self, table: QTableWidget) -> None:
            order_id = _selected_table_id(table, "pedido de compra")
            if order_id is None:
                QMessageBox.warning(self, "Compras", "Selecione um pedido de compra.")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Gerar conta a pagar")
            form = QFormLayout(dialog)
            account = QComboBox()
            category = QComboBox()
            cost_center = QComboBox()
            due_date = QDateEdit()
            due_date.setCalendarPopup(True)
            due_date.setDate(QDate.currentDate())
            with connect(settings.database_path) as connection:
                account.addItem("Sem conta definida", None)
                _fill_combo(account, list_financial_accounts(connection), "name")
                _fill_filter_combo(
                    category,
                    list_categories(connection, kind="expense"),
                    "Sem categoria",
                )
                _fill_filter_combo(cost_center, list_cost_centers(connection), "Sem centro")
            form.addRow("Conta", account)
            form.addRow("Categoria", category)
            form.addRow("Centro", cost_center)
            form.addRow("Vencimento", due_date)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                with connect(settings.database_path) as connection:
                    generate_purchase_payable(
                        connection,
                        purchase_order_id=order_id,
                        due_date=_qdate_to_date(due_date.date()),
                        account_id=_optional_combo_id(account),
                        category_id=_optional_combo_id(category),
                        cost_center_id=_optional_combo_id(cost_center),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Conta a pagar invalida", str(exc))
                return
            self._refresh_current_page()

        def _attach_document(self, entity_type: QComboBox, entity_id: QLineEdit) -> None:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar documento",
                str(settings.paths.documents_dir),
                "Documentos (*.pdf *.png *.jpg *.jpeg *.txt);;Todos os arquivos (*.*)",
            )
            if not file_path:
                return
            try:
                with connect(settings.database_path) as connection:
                    result = attach_document(
                        connection,
                        settings=settings,
                        source_path=Path(file_path),
                        entity_type=str(entity_type.currentData()),
                        entity_id=_positive_int(entity_id, "ID do vinculo"),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Documento invalido", str(exc))
                return
            QMessageBox.information(
                self,
                "Documento anexado",
                f"Documento #{result.document_id} vinculado com SHA-256:\n{result.sha256}",
            )
            self._refresh_current_page()

        def _open_selected_document(self, table: QTableWidget) -> None:
            row = table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Documentos", "Selecione um documento.")
                return
            path_item = table.item(row, 2)
            if path_item is None:
                QMessageBox.warning(self, "Documentos", "Documento invalido.")
                return
            path = settings.paths.resolve_app_path(path_item.text())
            if not path.is_file():
                QMessageBox.warning(self, "Documentos", "Arquivo anexado nao encontrado.")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

        def _apply_asaas_filters(
            self,
            status_filter: QComboBox,
            search_filter: QLineEdit,
            start_filter: QDateEdit,
            end_filter: QDateEdit,
        ) -> None:
            start_date = _qdate_to_date(start_filter.date())
            end_date = _qdate_to_date(end_filter.date())
            if start_date > end_date:
                QMessageBox.warning(self, "Filtros Asaas", "Data inicial maior que a final.")
                return
            status = status_filter.currentText()
            self._asaas_status_filter = "" if status == "Todos" else status
            self._asaas_search_filter = search_filter.text().strip()
            self._asaas_start_filter = start_date
            self._asaas_end_filter = end_date
            self._refresh_current_page()

        def _accept_selected_asaas_match(self, table: QTableWidget) -> None:
            row = table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Conciliacao", "Selecione uma sugestao.")
                return
            asaas_id_item = table.item(row, 0)
            transaction_id_item = table.item(row, 5)
            reason_item = table.item(row, 6)
            if asaas_id_item is None or transaction_id_item is None or reason_item is None:
                QMessageBox.warning(self, "Conciliacao", "Sugestao invalida.")
                return
            answer = QMessageBox.question(
                self,
                "Aceitar conciliacao",
                "Confirmar conciliacao entre a cobranca Asaas e o lancamento selecionado?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                with connect(settings.database_path) as connection:
                    accept_asaas_match(
                        connection,
                        asaas_id=asaas_id_item.text(),
                        transaction_id=int(transaction_id_item.text()),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                        confidence=100,
                        reason=reason_item.text(),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Conciliacao falhou", str(exc))
                return
            QMessageBox.information(self, "Conciliacao", "Conciliacao registrada.")
            self._refresh_current_page()

        def _cancel_selected_asaas_reconciliation(self, table: QTableWidget) -> None:
            row = table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Desconciliacao", "Selecione uma conciliacao.")
                return
            reconciliation_id_item = table.item(row, 5)
            if reconciliation_id_item is None:
                QMessageBox.warning(self, "Desconciliacao", "Conciliacao invalida.")
                return
            answer = QMessageBox.question(
                self,
                "Desconciliar",
                "Cancelar esta conciliacao? O historico sera preservado.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                with connect(settings.database_path) as connection:
                    cancel_asaas_reconciliation(
                        connection,
                        reconciliation_id=int(reconciliation_id_item.text()),
                        actor_user_id=get_session_user_id(connection, self._session_id),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Desconciliacao falhou", str(exc))
                return
            QMessageBox.information(self, "Desconciliacao", "Conciliacao cancelada.")
            self._refresh_current_page()

        def _load_sensitive_operations_table(
            self,
            table: QTableWidget,
            status_filter: QComboBox,
        ) -> None:
            with connect(settings.database_path) as connection:
                requests = list_sensitive_operation_requests(
                    connection,
                    status=_optional_combo_text(status_filter),
                )
            table.setRowCount(len(requests))
            for index, request in enumerate(requests):
                values = [
                    str(request.id),
                    _sensitive_status_label(request.status),
                    _sensitive_operation_label(request.operation_type),
                    request.title,
                    "" if request.amount_cents is None else format_brl_cents(request.amount_cents),
                    "" if request.external_reference is None else request.external_reference,
                    request.requested_username,
                    f"{request.approvals_count}/2",
                    str(request.rejections_count),
                ]
                for column, value in enumerate(values):
                    table.setItem(index, column, QTableWidgetItem(value))

        def _create_sensitive_operation_dialog(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Nova solicitacao sensivel")
            form = QFormLayout(dialog)
            operation = QComboBox()
            for label, value in [
                ("Criar cobranca Asaas", "asaas_create_charge"),
                ("Cancelar cobranca Asaas", "asaas_cancel_charge"),
                ("Estornar pagamento Asaas", "asaas_refund_payment"),
            ]:
                operation.addItem(label, value)
            title = QLineEdit()
            title.setPlaceholderText("Ex.: Criar cobranca de dizimo")
            amount = QLineEdit()
            amount.setPlaceholderText("Opcional, ex.: 150,00")
            external_reference = QLineEdit()
            external_reference.setPlaceholderText("Opcional")
            payload = QPlainTextEdit()
            payload.setMinimumHeight(150)

            def update_payload_template() -> None:
                templates = {
                    "asaas_create_charge": {
                        "customer_id": "preencher-id-cliente",
                        "description": "descricao sem credenciais",
                        "value_cents": 15000,
                    },
                    "asaas_cancel_charge": {
                        "asaas_id": "preencher-id-cobranca",
                        "reason": "motivo operacional",
                    },
                    "asaas_refund_payment": {
                        "asaas_id": "preencher-id-pagamento",
                        "reason": "motivo operacional",
                    },
                }
                payload.setPlainText(
                    json.dumps(
                        templates[str(operation.currentData())],
                        ensure_ascii=True,
                        indent=2,
                    )
                )

            operation.currentIndexChanged.connect(update_payload_template)
            update_payload_template()
            for label, widget in [
                ("Operacao", operation),
                ("Titulo", title),
                ("Valor", amount),
                ("Referencia externa", external_reference),
                ("Payload JSON", payload),
            ]:
                form.addRow(label, widget)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                payload_data = json.loads(payload.toPlainText())
                if not isinstance(payload_data, dict):
                    raise ValueError("Payload precisa ser um objeto JSON")
                amount_cents = (
                    None if not amount.text().strip() else parse_brl_to_cents(amount.text().strip())
                )
                with connect(settings.database_path) as connection:
                    request_id = create_sensitive_operation_request(
                        connection,
                        operation_type=str(operation.currentData()),
                        title=title.text(),
                        amount_cents=amount_cents,
                        external_reference=external_reference.text(),
                        payload=payload_data,
                        requested_by=self._current_user_id(),
                    )
            except (json.JSONDecodeError, ValueError) as exc:
                QMessageBox.warning(self, "Solicitacao invalida", str(exc))
                return
            QMessageBox.information(
                self,
                "Solicitacao criada",
                f"Solicitacao sensivel #{request_id} criada para aprovacao dupla.",
            )
            self._refresh_current_page()

        def _show_sensitive_operation_detail(self, table: QTableWidget) -> None:
            request_id = _selected_table_id(table, "solicitacao")
            if request_id is None:
                QMessageBox.warning(self, "Aprovacoes", "Selecione uma solicitacao.")
                return
            with connect(settings.database_path) as connection:
                selected = next(
                    request
                    for request in list_sensitive_operation_requests(connection)
                    if request.id == request_id
                )
                approvals = list_sensitive_operation_approvals(
                    connection,
                    request_id=request_id,
                )
                executions = list_sensitive_operation_executions(
                    connection,
                    request_id=request_id,
                )
                readiness = get_asaas_execution_readiness(
                    connection,
                    settings=settings,
                    request_id=request_id,
                )
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Solicitacao #{request_id}")
            dialog.setMinimumSize(620, 420)
            layout = QVBoxLayout(dialog)
            layout.addWidget(
                QLabel(
                    f"{_sensitive_operation_label(selected.operation_type)} | "
                    f"{_sensitive_status_label(selected.status)} | "
                    f"Solicitante: {selected.requested_username}"
                )
            )
            layout.addWidget(QLabel(selected.title))
            details = QPlainTextEdit()
            details.setReadOnly(True)
            approval_lines = [
                f"- {approval.approver_username}: "
                f"{_sensitive_decision_label(approval.decision)}"
                f" ({approval.created_at})" + (f" - {approval.notes}" if approval.notes else "")
                for approval in approvals
            ]
            approvals_text = "\n".join(approval_lines) if approval_lines else "Sem decisoes."
            execution_lines = [
                f"- #{execution.id}: {_sensitive_execution_status_label(execution.status)} | "
                f"idempotencia {execution.idempotency_key}"
                + (f" | externo {execution.external_id}" if execution.external_id else "")
                + (f" | erro {execution.error_message}" if execution.error_message else "")
                + (
                    "\n  resposta bruta omitida; use Exportar evidencia para revisao segura"
                    if execution.response
                    else ""
                )
                for execution in executions
            ]
            executions_text = (
                "\n".join(execution_lines) if execution_lines else "Sem tentativas de execucao."
            )
            readiness_text = (
                f"Pronta para Sandbox controlado.\nChave idempotente: {readiness.idempotency_key}"
                if readiness.ready
                else "\n".join(f"- {reason}" for reason in readiness.reasons)
            )
            details.setPlainText(
                "Payload aprovado localmente:\n"
                f"{json.dumps(selected.payload, ensure_ascii=True, indent=2)}\n\n"
                f"Decisoes:\n{approvals_text}\n\n"
                f"Prontidao de execucao:\n{readiness_text}\n\n"
                f"Execucoes:\n{executions_text}"
            )
            layout.addWidget(details)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            dialog.exec()

        def _export_sensitive_operation_readiness(self, table: QTableWidget) -> None:
            request_id = _selected_table_id(table, "solicitacao")
            if request_id is None:
                QMessageBox.warning(self, "Aprovacoes", "Selecione uma solicitacao.")
                return
            default_path = (
                settings.paths.documents_dir / "exports" / f"prontidao-asaas-{request_id}.json"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar prontidao Asaas",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            output_path = Path(path)
            with connect(settings.database_path) as connection:
                payload = build_asaas_execution_readiness_json(
                    connection,
                    settings=settings,
                    request_id=request_id,
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            QMessageBox.information(
                self,
                "Prontidao exportada",
                "Prontidao local exportada sem token e sem chamada externa.",
            )

        def _export_sensitive_operation_execution_report(self, table: QTableWidget) -> None:
            request_id = _selected_table_id(table, "solicitacao")
            if request_id is None:
                QMessageBox.warning(self, "Aprovacoes", "Selecione uma solicitacao.")
                return
            default_path = (
                settings.paths.documents_dir / "exports" / f"evidencia-asaas-{request_id}.json"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar evidencia Asaas",
                str(default_path),
                "JSON (*.json)",
            )
            if not path:
                return
            output_path = Path(path)
            with connect(settings.database_path) as connection:
                payload = build_asaas_execution_report_json(
                    connection,
                    settings=settings,
                    request_id=request_id,
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            QMessageBox.information(
                self,
                "Evidencia exportada",
                "Evidencia local exportada sem token, payload ou resposta bruta da API.",
            )

        def _export_sensitive_operation_validation_package(self, table: QTableWidget) -> None:
            request_id = _selected_table_id(table, "solicitacao")
            if request_id is None:
                QMessageBox.warning(self, "Aprovacoes", "Selecione uma solicitacao.")
                return
            default_path = (
                settings.paths.documents_dir
                / "exports"
                / f"pacote-homologacao-asaas-{request_id}.zip"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar pacote de homologacao Asaas",
                str(default_path),
                "ZIP (*.zip)",
            )
            if not path:
                return
            output_path = Path(path)
            with connect(settings.database_path) as connection:
                write_asaas_sandbox_validation_package(
                    connection,
                    settings=settings,
                    request_id=request_id,
                    output_path=output_path,
                )
            QMessageBox.information(
                self,
                "Pacote exportado",
                "Pacote local exportado com prontidao, evidencia, checklist e manifesto.",
            )

        def _export_sensitive_operation_review_summary(self, table: QTableWidget) -> None:
            request_id = _selected_table_id(table, "solicitacao")
            if request_id is None:
                QMessageBox.warning(self, "Aprovacoes", "Selecione uma solicitacao.")
                return
            exports_dir = settings.paths.documents_dir / "exports"
            default_path = exports_dir / f"resumo-aceite-asaas-{request_id}.md"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar resumo de aceite Asaas",
                str(default_path),
                "Markdown (*.md)",
            )
            if not path:
                return
            output_path = Path(path)
            package_path = output_path.with_name(f"pacote-homologacao-asaas-{request_id}.zip")
            with connect(settings.database_path) as connection:
                write_asaas_sandbox_validation_package(
                    connection,
                    settings=settings,
                    request_id=request_id,
                    output_path=package_path,
                )
            summary = build_asaas_sandbox_validation_review_summary_markdown(
                package_path=package_path,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(summary, encoding="utf-8")
            QMessageBox.information(
                self,
                "Resumo exportado",
                "Resumo de aceite exportado com gates locais e sem dados sensiveis.",
            )

        def _execute_selected_sensitive_operation_sandbox(self, table: QTableWidget) -> None:
            request_id = _selected_table_id(table, "solicitacao")
            if request_id is None:
                QMessageBox.warning(self, "Aprovacoes", "Selecione uma solicitacao.")
                return
            if settings.asaas_env.strip().lower() != "sandbox":
                QMessageBox.warning(
                    self,
                    "Execucao bloqueada",
                    "Execucao pela UI e permitida somente com ASAAS_ENV=sandbox.",
                )
                return
            answer = QMessageBox.question(
                self,
                "Executar no Asaas Sandbox",
                (
                    f"Executar a solicitacao #{request_id} no Asaas Sandbox?\n\n"
                    "Confirme apenas se a chave Sandbox esta no .env local, "
                    "a operacao recebeu duas aprovacoes e a prontidao foi revisada."
                ),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            if not self._confirm_sandbox_execution_phrase(request_id):
                return
            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                with connect(settings.database_path) as connection:
                    execution = execute_approved_asaas_operation(
                        connection,
                        settings=settings,
                        request_id=request_id,
                        actor_user_id=self._current_user_id(),
                        transport=urllib_asaas_write_transport,
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Execucao Asaas bloqueada", str(exc))
                return
            finally:
                QApplication.restoreOverrideCursor()
            QMessageBox.information(
                self,
                "Execucao Sandbox registrada",
                (
                    f"Status local: {_sensitive_execution_status_label(execution.status)}.\n"
                    f"Execucao: #{execution.id}.\n"
                    "Use Exportar evidencia, Exportar pacote e Exportar resumo para revisao."
                ),
            )
            self._refresh_current_page()

        def _confirm_sandbox_execution_phrase(self, request_id: int) -> bool:
            dialog = QDialog(self)
            dialog.setWindowTitle("Confirmar Sandbox")
            form = QFormLayout(dialog)
            form.addRow(QLabel(f"Para executar a solicitacao #{request_id}, digite SANDBOX."))
            confirmation = QLineEdit()
            confirmation.setPlaceholderText("SANDBOX")
            form.addRow("Confirmacao", confirmation)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            if confirmation.text().strip().upper() != "SANDBOX":
                QMessageBox.warning(
                    self,
                    "Confirmacao invalida",
                    "Execucao cancelada: a confirmacao digitada nao foi SANDBOX.",
                )
                return False
            return True

        def _decide_selected_sensitive_operation(
            self,
            table: QTableWidget,
            decision: str,
        ) -> None:
            request_id = _selected_table_id(table, "solicitacao")
            if request_id is None:
                QMessageBox.warning(self, "Aprovacoes", "Selecione uma solicitacao.")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle(_sensitive_decision_label(decision))
            form = QFormLayout(dialog)
            notes = QPlainTextEdit()
            notes.setMinimumHeight(90)
            form.addRow("Observacao", notes)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            answer = QMessageBox.question(
                self,
                _sensitive_decision_label(decision),
                f"Registrar decisao para a solicitacao #{request_id}?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                with connect(settings.database_path) as connection:
                    updated = approve_sensitive_operation_request(
                        connection,
                        request_id=request_id,
                        approver_user_id=self._current_user_id(),
                        decision=decision,
                        notes=notes.toPlainText(),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Decisao nao registrada", str(exc))
                return
            QMessageBox.information(
                self,
                "Decisao registrada",
                f"Status atual: {_sensitive_status_label(updated.status)}.",
            )
            self._refresh_current_page()

        def _cancel_selected_sensitive_operation(self, table: QTableWidget) -> None:
            request_id = _selected_table_id(table, "solicitacao")
            if request_id is None:
                QMessageBox.warning(self, "Aprovacoes", "Selecione uma solicitacao.")
                return
            answer = QMessageBox.question(
                self,
                "Cancelar solicitacao",
                f"Cancelar a solicitacao sensivel #{request_id}?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                with connect(settings.database_path) as connection:
                    cancel_sensitive_operation_request(
                        connection,
                        request_id=request_id,
                        actor_user_id=self._current_user_id(),
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Cancelamento falhou", str(exc))
                return
            QMessageBox.information(self, "Aprovacoes", "Solicitacao cancelada.")
            self._refresh_current_page()

        def _export_financial_report(self, file_type: str) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Exportar relatorio financeiro")
            form = QFormLayout(dialog)
            start_date = QDateEdit()
            start_date.setCalendarPopup(True)
            start_date.setDate(QDate.currentDate().addDays(-30))
            end_date = QDateEdit()
            end_date.setCalendarPopup(True)
            end_date.setDate(QDate.currentDate())
            form.addRow("Inicio", start_date)
            form.addRow("Fim", end_date)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            end_value = _qdate_to_date(end_date.date()).isoformat()
            default_name = f"relatorio-financeiro-{end_value}.{file_type}"
            file_filters = {
                "xlsx": "Planilhas Excel (*.xlsx)",
                "csv": "CSV (*.csv)",
                "pdf": "PDF (*.pdf)",
            }
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar relatorio",
                str(settings.paths.documents_dir / "exports" / default_name),
                file_filters[file_type],
            )
            if not output_path:
                return
            try:
                with connect(settings.database_path) as connection:
                    report_path = Path(output_path)
                    start_value = _qdate_to_date(start_date.date())
                    end_report_value = _qdate_to_date(end_date.date())
                    if file_type == "xlsx":
                        created_path = export_financial_report_xlsx(
                            connection,
                            output_path=report_path,
                            start_date=start_value,
                            end_date=end_report_value,
                        )
                    elif file_type == "csv":
                        created_path = export_financial_report_csv(
                            connection,
                            output_path=report_path,
                            start_date=start_value,
                            end_date=end_report_value,
                        )
                    else:
                        created_path = export_financial_report_pdf(
                            connection,
                            output_path=report_path,
                            start_date=start_value,
                            end_date=end_report_value,
                        )
            except ValueError as exc:
                QMessageBox.warning(self, "Relatorio nao exportado", str(exc))
                return
            QMessageBox.information(
                self,
                "Relatorio exportado",
                f"Arquivo gerado em:\n{created_path}",
            )

    app = QApplication([])
    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(font_file))
    app.setStyleSheet(app_stylesheet())
    login = LoginWindow()
    login.setWindowFlag(Qt.WindowType.Window)
    login.show()
    if screenshot_path is not None:
        QTimer.singleShot(25, lambda: _capture_widget(login, screenshot_path))
    if auto_quit_ms is not None:
        QTimer.singleShot(auto_quit_ms, app.quit)
    return app.exec()


def _stylesheet() -> str:
    return app_stylesheet()


def _field_label(text: str) -> Any:
    from PySide6.QtWidgets import QLabel

    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def _centered_widget(widget: Any) -> Any:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHBoxLayout, QWidget

    wrapper = QWidget()
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(widget)
    return wrapper


def _right_aligned_widget(widget: Any) -> Any:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHBoxLayout, QWidget

    wrapper = QWidget()
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 12, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(widget)
    return wrapper


def _build_row_checkbox_widget() -> Any:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QWidget

    wrapper = QWidget()
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    checkbox = QCheckBox()
    layout.addWidget(checkbox)
    return wrapper


def _selected_row_id_from_column(table: Any, column: int) -> int | None:
    from PySide6.QtCore import Qt

    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, column)
    if item is None:
        return None
    value = item.data(Qt.ItemDataRole.UserRole)
    return None if value is None else int(value)


def _transaction_signed_value(transaction_type: str, amount_cents: int) -> int:
    if transaction_type == "revenue":
        return amount_cents
    if transaction_type == "transfer_in":
        return amount_cents
    return -amount_cents


def _format_signed_brl(amount_cents: int) -> str:
    prefix = "+" if amount_cents > 0 else "-"
    if amount_cents == 0:
        prefix = ""
    return f"{prefix} {format_brl_cents(abs(amount_cents))}".strip()


def _transaction_value_color(transaction_type: str) -> str:
    if transaction_type in {"revenue", "transfer_in"}:
        return COLORS.green
    return COLORS.red


def _transaction_badge(transaction_type: str) -> Any:
    from basilica_financeiro.ui.components import BadgeLabel

    tone_map = {
        "revenue": ("Receita", "income"),
        "expense": ("Despesa", "expense"),
        "transfer_in": ("Transferencia", "transfer"),
        "transfer_out": ("Transferencia", "transfer"),
    }
    label, tone = tone_map.get(transaction_type, ("Lancamento", "pending"))
    return BadgeLabel(label, tone, show_dot=True)


def _filter_transaction_rows(
    rows: list[Any],
    *,
    transaction_tab: str,
    period: str,
    today: date,
) -> list[Any]:
    start_date = today.replace(day=1)
    if period == "week":
        start_date = today - timedelta(days=today.weekday())
    elif period == "year":
        start_date = date(today.year, 1, 1)
    elif period == "custom":
        start_date = today - timedelta(days=90)

    def include_type(transaction_type: str) -> bool:
        if transaction_tab == "all":
            return True
        if transaction_tab == "transfer":
            return transaction_type.startswith("transfer")
        return transaction_type == transaction_tab

    filtered: list[Any] = []
    for row in rows:
        transaction_date = date.fromisoformat(str(row["effective_date"]))
        transaction_type = str(row["transaction_type"])
        if transaction_date < start_date:
            continue
        if include_type(transaction_type):
            filtered.append(row)
    return filtered


def _account_type_label(account_type: str) -> str:
    labels = {
        "checking": "Conta corrente",
        "cash": "Caixa",
        "payment": "Pagamento",
        "asaas": "Asaas",
        "card": "Cartao",
        "investment": "Investimento",
    }
    return labels.get(account_type, account_type)


def _account_status_label(status: str) -> str:
    labels = {
        "active": "Ativa",
        "inactive": "Inativa",
        "archived": "Arquivada",
    }
    return labels.get(status, status)


def _due_entry_badge(*, entry_type: str, effective_status: str, due_date: str) -> Any:
    from basilica_financeiro.ui.components import BadgeLabel

    if effective_status == "paid":
        return BadgeLabel("Pago", "paid")
    if effective_status == "canceled":
        return BadgeLabel("Cancelado", "cancelled", show_dot=False)
    if effective_status == "partial":
        return BadgeLabel("Pendente", "pending")
    due_value = date.fromisoformat(due_date)
    if due_value < date.today():
        return BadgeLabel("Vencido", "overdue")
    if (due_value - date.today()).days <= 7:
        return BadgeLabel("A vencer", "due-soon")
    if entry_type == "receivable":
        return BadgeLabel("Em aberto", "open")
    return BadgeLabel("Em aberto", "open")


def _capture_widget(widget: Any, screenshot_path: Path) -> None:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(screenshot_path))


def _fill_combo(
    combo: Any,
    rows: list[Any],
    label_key: str,
    *,
    include_empty: bool = False,
) -> None:
    if include_empty:
        combo.addItem("Sem centro", None)
    for row in rows:
        combo.addItem(str(row[label_key]), int(row["id"]))


def _fill_filter_combo(combo: Any, rows: list[Any], empty_label: str) -> None:
    combo.addItem(empty_label, None)
    for row in rows:
        combo.addItem(str(row["name"]), int(row["id"]))


def _required_combo_id(combo: Any, field_label: str) -> int:
    value = combo.currentData()
    if value is None:
        raise ValueError(f"{field_label} precisa ser selecionado")
    return int(value)


def _selected_table_id(table: Any, entity_label: str) -> int | None:
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    if item is None:
        return None
    return int(item.text())


def _optional_combo_id(combo: Any) -> int | None:
    value = combo.currentData()
    return None if value is None else int(value)


def _optional_combo_text(combo: Any) -> str | None:
    value = combo.currentData()
    return None if value is None else str(value)


def _short_label(value: str, *, limit: int = 18) -> str:
    return value if len(value) <= limit else f"{value[: limit - 1]}..."


def _sensitive_operation_label(value: str) -> str:
    labels = {
        "asaas_create_charge": "Criar cobranca Asaas",
        "asaas_cancel_charge": "Cancelar cobranca Asaas",
        "asaas_refund_payment": "Estornar pagamento Asaas",
    }
    return labels.get(value, value)


def _sensitive_status_label(value: str) -> str:
    labels = {
        "pending": "Pendente",
        "approved": "Aprovada",
        "rejected": "Rejeitada",
        "canceled": "Cancelada",
        "executed": "Executada",
    }
    return labels.get(value, value)


def _sensitive_decision_label(value: str) -> str:
    labels = {
        "approved": "Aprovar",
        "rejected": "Rejeitar",
    }
    return labels.get(value, value)


def _sensitive_execution_status_label(value: str) -> str:
    labels = {
        "succeeded": "Sucesso",
        "failed": "Falha",
    }
    return labels.get(value, value)


def _dashboard_period(
    period_preset: str,
    *,
    today: date,
    custom_start: date,
    custom_end: date,
) -> tuple[date, date]:
    if period_preset == "current_month":
        return today.replace(day=1), today
    if period_preset == "last_30_days":
        return today - timedelta(days=29), today
    if period_preset == "current_year":
        return date(today.year, 1, 1), today
    return custom_start, custom_end


def _select_combo_data(combo: Any, value: int) -> None:
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            combo.setCurrentIndex(index)
            return


def _required_text(line_edit: Any, field_label: str) -> str:
    value = str(line_edit.text()).strip()
    if not value:
        raise ValueError(f"{field_label} precisa ser preenchido")
    return value


def _positive_int(line_edit: Any, field_label: str) -> int:
    try:
        value = int(line_edit.text())
    except ValueError as exc:
        raise ValueError(f"{field_label} precisa ser um numero inteiro") from exc
    if value < 1:
        raise ValueError(f"{field_label} precisa ser maior que zero")
    return value


def _monthly_weights_from_inputs(inputs: list[Any], *, enabled: bool) -> list[int] | None:
    if not enabled:
        return None
    weights = []
    for index, line_edit in enumerate(inputs, start=1):
        try:
            weight = int(str(line_edit.text()).strip())
        except ValueError as exc:
            raise ValueError(f"Peso do mes {index} precisa ser um numero inteiro") from exc
        if weight < 1:
            raise ValueError(f"Peso do mes {index} precisa ser maior que zero")
        weights.append(weight)
    return weights


def _dict_int(row: dict[str, object], key: str) -> int:
    value = row[key]
    if not isinstance(value, int):
        raise TypeError(f"Campo {key} deveria ser inteiro")
    return value


def _qdate_to_date(value: Any) -> date:
    return date(value.year(), value.month(), value.day())
