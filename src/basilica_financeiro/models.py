from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class BackupHistory(Base):
    __tablename__ = "backup_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Role(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Permission(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_name: Mapped[str] = mapped_column(ForeignKey("roles.name"), primary_key=True)
    permission_code: Mapped[str] = mapped_column(ForeignKey("permissions.code"), primary_key=True)


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String, nullable=False)
    institution: Mapped[str | None] = mapped_column(String, nullable=True)
    masked_number: Mapped[str | None] = mapped_column(String, nullable=True)
    opening_balance_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_balance_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_date: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    integration_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class CostCenter(Base):
    __tablename__ = "cost_centers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("financial_accounts.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="posted")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[str] = mapped_column(String, nullable=False)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    paid_at: Mapped[str | None] = mapped_column(String, nullable=True)
    transfer_group_id: Mapped[str | None] = mapped_column(String, nullable=True)
    series_group_id: Mapped[str | None] = mapped_column(String, nullable=True)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recurrence_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class PayableReceivableEntry(Base):
    __tablename__ = "payable_receivable_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_type: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_accounts.id"),
        nullable=True,
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"), nullable=True)
    counterparty: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_date: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    paid_at: Mapped[str | None] = mapped_column(String, nullable=True)
    settlement_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transactions.id"),
        nullable=True,
    )
    series_group_id: Mapped[str | None] = mapped_column(String, nullable=True)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recurrence_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class AsaasPayment(Base):
    __tablename__ = "asaas_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asaas_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    value_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    net_value_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_date: Mapped[str | None] = mapped_column(String, nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class AsaasReconciliation(Base):
    __tablename__ = "asaas_reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asaas_id: Mapped[str] = mapped_column(ForeignKey("asaas_payments.asaas_id"), nullable=False)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("financial_transactions.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="accepted")
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class PdvCategory(Base):
    __tablename__ = "pdv_categories"

    pdv_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class PdvProduct(Base):
    __tablename__ = "pdv_products"

    pdv_id: Mapped[str] = mapped_column(String, primary_key=True)
    category_pdv_id: Mapped[str | None] = mapped_column(
        ForeignKey("pdv_categories.pdv_id"),
        nullable=True,
    )
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stock_value_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class PdvSale(Base):
    __tablename__ = "pdv_sales"

    pdv_id: Mapped[str] = mapped_column(String, primary_key=True)
    sold_at: Mapped[str] = mapped_column(String, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    imported_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transactions.id"),
        nullable=True,
    )
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
