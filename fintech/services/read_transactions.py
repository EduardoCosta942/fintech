import psycopg2
from typing import Optional
from langchain.tools import tool
from dataclasses import dataclass
from pydantic import Field, validator

from ..logger import log_error, log_debug, log_info, log_warning
from ..env_loader import get_env_variable
from ..models import Transaction
from ..enum import ReadTransactionsFilter
from ..exceptions import UnavalableFilterError, UnresolvedVariableError
from .utils import ALIASES, ALIAS_SERVICE, Database

def _normalize_read_transactions_filter(value) -> ReadTransactionsFilter:
    if isinstance(value, ReadTransactionsFilter):
        return value

    if isinstance(value, int):
        try:
            return ReadTransactionsFilter(value)
        except ValueError:
            raise UnavalableFilterError(f"Filter not available: {value}")

    if isinstance(value, str):
        text = value.strip()

        if text.isdigit():
            try:
                return ReadTransactionsFilter(int(text))
            except ValueError:
                raise UnavalableFilterError(f"Filter not available: {value}")

        try:
            return ReadTransactionsFilter[text.upper()]
        except KeyError:
            raise UnavalableFilterError(f"Filter not available: {value}")

    raise UnavalableFilterError(f"Filter not available: {value}")

def _format_occurred_at(value):
    if value is None:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)

class ReadTransactionArgs(Transaction):
    readTransactionsFilter: ReadTransactionsFilter
    type_name: Optional[str] = None
    category_name: Optional[str] = None
    last_days: Optional[int] = None
    source_text: None = Field(default=None, exclude=True)

    @validator("source_text", pre=True, always=True)
    def block_source_text(cls, v):
        if v is not None:
            raise ValueError("source_text não pode ser usado aqui")
        return v


@tool("search_transactions", args_schema=ReadTransactionArgs)
def search_transactions(
    readTransactionsFilter: ReadTransactionsFilter,
    amount: float = None,
    source_text: str = None,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None, # not in database
    category_id: Optional[int] = None,
    category_name: Optional[str] = None, # not in database
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
    last_days: Optional[int] = None
) -> dict:
    """Essa ferramenta retorna uma lista de objetos Transaction encontrados no banco de dados. O único parametro obrigatório é o readTransactionsFilter, que indica qual filtro deve ser aplicado:
        - GENERIC: Retorna transações que correspondem a qualquer um dos parâmetros fornecidos (amount, source_text, occurred_at, type_id, type_name, category_id). 
        - LAST_DAYS: Retorna transações ocorridas nos últimos N dias (use o parâmetro last_days para indicar o número de dias).
        - AMOUNT_GREATER_THAN: Retorna transações com valor maior que o especificado
        - AMOUNT_LOWER_THAN: Retorna transações com valor menor que o especificado
        Observa-se que o parametro readTransactionsFilter é um enum e deve ser indicado como

        Exemplo de uso dos filtros:
        User: Quanto que eu já gastei com comida?
        Entao, o assistente usa o filtro GENERIC, indicando a categoria "comida" (category_id ou category_name)
    """
    log_info("Executing read_transactions tool")

    readTransactionsFilter = _normalize_read_transactions_filter(readTransactionsFilter)
    log_debug(f"Normalized filter: {readTransactionsFilter.name} ({readTransactionsFilter.value})")

    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            try:
                filters = []
                params = []

                if readTransactionsFilter == ReadTransactionsFilter.GENERIC:
                    if amount is not None:
                        filters.append("amount = %s")
                        params.append(amount)
                    if occurred_at is not None:
                        filters.append("occurred_at = %s")
                        params.append(occurred_at)
                    if type_id is not None or type_name is not None:
                        resolved_type_id = ALIAS_SERVICE.resolve_type_id(type_id=type_id, type_name=type_name)
                        if resolved_type_id is None:
                            string = ""
                            for key, value in ALIASES["type_aliases"].items():
                                string += f"{value} (id: {key}); "

                            error = UnresolvedVariableError({
                                "status": "error",
                                "message": f"Invalid type (use type_name or type_id: {string.rstrip('; ')})"
                            })

                            log_warning("Transaction rejected due to invalid type")
                            raise error

                        filters.append("(type = %s)")
                        params.append(resolved_type_id)
                    if category_id is not None or category_name is not None:
                        resolved_category_id = ALIAS_SERVICE.resolve_category_id(category_id=category_id, category_name=category_name)

                        if not resolved_category_id:
                            string = ""
                            for key, value in ALIASES["category_aliases"].items():
                                string += f"{value} (id: {key}); "

                            error = UnresolvedVariableError({
                                "status": "error",
                                "message": f"Invalid category_id (use category_id: {string.rstrip('; ')})"
                            })

                            log_warning("Transaction rejected due to invalid category_id")
                            raise error

                        filters.append("category_id = %s")
                        params.append(resolved_category_id)
                    if payment_method is not None:
                        filters.append("payment_method ILIKE %s")
                        params.append(f"%{payment_method}%")

                elif readTransactionsFilter == ReadTransactionsFilter.LAST_DAYS:
                    if last_days is not None:
                        filters.append("occurred_at >= CURRENT_DATE - (%s * INTERVAL '1 day')")
                        params.append(last_days)

                elif readTransactionsFilter == ReadTransactionsFilter.AMOUNT_GREATER_THAN:
                    if amount is not None:
                        filters.append("amount > %s")
                        params.append(amount)

                elif readTransactionsFilter == ReadTransactionsFilter.AMOUNT_LOWER_THAN:
                    if amount is not None:
                        filters.append("amount < %s")
                        params.append(amount)
                else:
                    raise UnavalableFilterError(f"Filter not available: {readTransactionsFilter}")

                query = """
                    SELECT id, amount, type, category_id, description, payment_method, occurred_at, source_text
                    FROM transactions
                """
                if filters:
                    query += " WHERE " + " AND ".join(filters)

                log_debug(f"Executing SQL: {query}")
                cur.execute(query, params)
                results = cur.fetchall()

                log_info(f"read_transactions returned {len(results)} results")
                result = [
                    dict(
                        readTransactionsFilter=readTransactionsFilter,
                        amount=row[1],
                        source_text=row[7],
                        occurred_at=_format_occurred_at(row[6]),
                        type_id=row[2],
                        category_id=row[3],
                        description=row[4],
                        payment_method=row[5]
                    )
                    for row in results
                ]

                if not result:
                    return {"message": "No transactions found matching the criteria."}
                return result

            except Exception as e:
                log_error(str(e))
                conn.rollback()
                return {"status": "error", "message": str(e)}
