from __future__ import annotations


def parse_brl_to_cents(value: str) -> int:
    cleaned = value.strip().replace("R$", "").replace(" ", "")
    if not cleaned:
        raise ValueError("Valor monetario vazio")
    normalized = cleaned.replace(".", "").replace(",", ".")
    if normalized.count(".") > 1:
        raise ValueError("Valor monetario invalido")
    parts = normalized.split(".")
    reais = parts[0] or "0"
    cents = parts[1] if len(parts) == 2 else "0"
    if len(cents) > 2 or not reais.lstrip("-").isdigit() or not cents.isdigit():
        raise ValueError("Valor monetario invalido")
    amount_cents = int(reais) * 100
    amount_cents += int(cents.ljust(2, "0")) if amount_cents >= 0 else -int(cents.ljust(2, "0"))
    return amount_cents


def format_brl_cents(value_cents: int) -> str:
    sign = "-" if value_cents < 0 else ""
    absolute = abs(value_cents)
    reais = absolute // 100
    cents = absolute % 100
    reais_text = f"{reais:,}".replace(",", ".")
    return f"{sign}R$ {reais_text},{cents:02d}"
