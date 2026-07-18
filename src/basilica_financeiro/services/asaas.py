from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from basilica_financeiro.services.money import parse_float_to_cents


class AsaasTransport(Protocol):
    def __call__(
        self,
        *,
        url: str,
        headers: dict[str, str],
        params: dict[str, str | int],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        pass


@dataclass(frozen=True)
class AsaasPayment:
    asaas_id: str
    status: str
    value_cents: int
    net_value_cents: int | None
    due_date: date | None
    payment_date: date | None
    customer_name: str | None
    description: str | None
    billing_type: str | None
    external_reference: str | None
    raw: dict[str, Any]


class AsaasClient:
    def __init__(
        self,
        *,
        api_key: str,
        environment: str,
        transport: AsaasTransport | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        if not api_key.strip():
            raise ValueError("ASAAS_API_KEY precisa estar configurada no .env")
        self._api_key = api_key
        self._base_url = asaas_base_url(environment)
        self._transport = transport or _urllib_get_json
        self._timeout_seconds = timeout_seconds

    def list_payments(
        self,
        *,
        due_date_start: date | None = None,
        due_date_end: date | None = None,
        limit: int = 100,
    ) -> list[AsaasPayment]:
        if limit < 1 or limit > 100:
            raise ValueError("Limite por pagina precisa ficar entre 1 e 100")
        params: dict[str, str | int] = {"limit": limit, "offset": 0}
        if due_date_start is not None:
            params["dueDate[ge]"] = due_date_start.isoformat()
        if due_date_end is not None:
            params["dueDate[le]"] = due_date_end.isoformat()

        output: list[AsaasPayment] = []
        while True:
            payload = self._transport(
                url=f"{self._base_url}/payments",
                headers={
                    "accept": "application/json",
                    "access_token": self._api_key,
                    "user-agent": "basilica-financeiro/0.1",
                },
                params=params,
                timeout_seconds=self._timeout_seconds,
            )
            rows = payload.get("data", [])
            if not isinstance(rows, list):
                raise ValueError("Resposta do Asaas sem lista de cobrancas")
            output.extend(_payment_from_payload(row) for row in rows if isinstance(row, dict))
            has_more = bool(payload.get("hasMore"))
            if not has_more:
                return output
            params["offset"] = int(params["offset"]) + limit


def asaas_base_url(environment: str) -> str:
    normalized = environment.strip().lower()
    if normalized == "production":
        return "https://api.asaas.com/v3"
    if normalized == "sandbox":
        return "https://api-sandbox.asaas.com/v3"
    raise ValueError("ASAAS_ENV precisa ser sandbox ou production")


def _urllib_get_json(
    *,
    url: str,
    headers: dict[str, str],
    params: dict[str, str | int],
    timeout_seconds: int,
) -> dict[str, Any]:
    if not url.startswith("https://"):
        raise ValueError("Asaas requer HTTPS")
    query = urlencode(params)
    request = Request(f"{url}?{query}", headers=headers, method="GET")  # noqa: S310
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        raise ValueError(f"Asaas retornou HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError("Asaas indisponivel no momento") from exc
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("Resposta do Asaas em formato inesperado")
    return parsed


def _payment_from_payload(payload: dict[str, Any]) -> AsaasPayment:
    asaas_id = _required_text(payload, "id")
    value_cents = parse_float_to_cents(payload.get("value"))
    net_value_cents = _optional_decimal_to_cents(payload.get("netValue"))
    return AsaasPayment(
        asaas_id=asaas_id,
        status=_required_text(payload, "status"),
        value_cents=value_cents,
        net_value_cents=net_value_cents,
        due_date=_optional_date(payload.get("dueDate")),
        payment_date=_optional_date(payload.get("paymentDate")),
        customer_name=_optional_text(payload.get("customerName")),
        description=_optional_text(payload.get("description")),
        billing_type=_optional_text(payload.get("billingType")),
        external_reference=_optional_text(payload.get("externalReference")),
        raw=payload,
    )


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Cobranca Asaas sem campo obrigatorio: {key}")
    return value.strip()


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return date.fromisoformat(value.strip())


def _optional_decimal_to_cents(value: object) -> int | None:
    return None if value is None else parse_float_to_cents(value)
