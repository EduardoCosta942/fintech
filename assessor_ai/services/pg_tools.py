from typing import List, Optional, Union
from datetime import datetime
from dataclasses import dataclass

from pydantic import BaseModel, Field, validator
from langchain.tools import tool

from ..enum import ReadTransactionsFilter
from ..exceptions import MissingArgumentError, UnavalableFilterError, UnresolvedVariableError, InvalidAliasError
from ..logger import log_error, log_debug, log_info, log_warning
from ..models import Transaction
    
from .utils import ALIASES, ALIAS_SERVICE, Database, format_date

def _resolve_alias_id_or_raise(
    *,
    label: str,
    alias_dict_key: str,
    raw_id: Optional[int],
    raw_name: Optional[str],
) -> int:
    """Resolve type/category IDs and raise semantic exceptions when invalid.

    Rules:
    - If both id and name are missing, raise UnresolvedVariableError.
    - If a value is provided but cannot be resolved by aliases, raise InvalidAliasError.
    """
    if raw_id is None and not raw_name:
        raise UnresolvedVariableError(
            f"Unresolved {label}: provide either {label}_id or {label}_name"
        )

    if label == "type":
        resolved_id = ALIAS_SERVICE.resolve_type_id(type_name=raw_name, type_id=raw_id)
    else:
        resolved_id = ALIAS_SERVICE.resolve_category_id(category_id=raw_id, category_name=raw_name)

    if not resolved_id:
        raise InvalidAliasError(
            alias=ALIASES[alias_dict_key],
            base_message=f"Invalid {label}",
        )

    return resolved_id

@dataclass
class AddTransactionArgs(Transaction):
    amount: float = Field(..., description="Valor da transação.") # Set mandatory
    source_text: str = Field(..., description="Texto de origem da transação.") # Set mandatory
    description: str = Field(..., description="Descrição da transação.") # Set mandatory
    type_name: Optional[str] = Field(default=None, description="Nome do tipo: INCOME | EXPENSES | TRANSFER") # External representation of type_id
    category_name: Optional[str] = Field(default=None, description="Nome da categoria da transação.") # External representation of category_id

@tool("add_transaction", args_schema=AddTransactionArgs)
def add_transaction(
    amount: float,
    source_text: str,
    category_id: Optional[int],
    type_id: Optional[int],
    occurred_at: Optional[str] = None,
    type_name: Optional[str] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
    """Insere uma transação financeira no Postgres.

    Parâmetros
    ----------
    amount : float
        Valor da transação.
    source_text : str
        Texto de origem (mensagem do usuário).
    category_id/type_id : Optional[int]
        IDs diretos para categoria/tipo.
    occurred_at : Optional[str]
        Data em formato aceito por `format_date`.
    type_name/category_name : Optional[str]
        Alias textual para resolver `type_id` e `category_id`.

    Retorno
    -------
    dict
        Resultado com status, id e data da transação.
    """

    log_info("Starting transaction insertion")
    log_debug(f"Received arguments: amount={amount}, source_text='{source_text}', category_id={category_id}, type_id={type_id}, occurred_at='{occurred_at}', type_name='{type_name}', description='{description}', payment_method='{payment_method}'")

    log_debug(f"Type aliases: {ALIASES['type_aliases']}")
    log_debug(f"Category aliases: {ALIASES['category_aliases']}")

    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            try:
                if amount is None:
                    raise MissingArgumentError("Missing required argument: amount")
                if not source_text:
                    raise MissingArgumentError("Missing required argument: source_text")
                if not description:
                    raise MissingArgumentError("Missing required argument: description")

                if type_id is not None and type_name:
                    log_warning("Both type_id and type_name were provided; type_id will be prioritized when valid")

                resolved_type_id = _resolve_alias_id_or_raise(
                    label="type",
                    alias_dict_key="type_aliases",
                    raw_id=type_id,
                    raw_name=type_name,
                )

                if category_id is not None and category_name:
                    log_warning("Both category_id and category_name were provided; category_id will be prioritized when valid")

                resolved_category_id = _resolve_alias_id_or_raise(
                    label="category",
                    alias_dict_key="category_aliases",
                    raw_id=category_id,
                    raw_name=category_name,
                )

                log_debug("Executing INSERT into transactions")

                if amount < 0:
                    log_warning(f"Tried to insert transaction with negative amount ({amount}). Multiplying  by -1 to convert to positive.")
                    amount = -amount

                if occurred_at:
                    occurred_at = format_date(occurred_at)
                    cur.execute(
                        """
                        INSERT INTO transactions
                            (amount, type, category_id, description, payment_method, occurred_at, source_text)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, occurred_at;
                        """,
                        (amount, resolved_type_id, resolved_category_id, description, payment_method, occurred_at, source_text),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO transactions
                            (amount, type, category_id, description, payment_method, occurred_at, source_text)
                        VALUES
                            (%s, %s, %s, %s, %s, NOW(), %s)
                        RETURNING id, occurred_at;
                        """,
                        (amount, resolved_type_id, resolved_category_id, description, payment_method, source_text),
                    )

                new_id, occurred = cur.fetchone()
                conn.commit()

                log_info(f"Transaction inserted successfully | id: {new_id}")

                return {"status": "ok", "id": new_id, "occurred_at": str(occurred)}

            except (MissingArgumentError, UnresolvedVariableError, InvalidAliasError) as e:
                log_warning(f"Transaction insertion rejected due to invalid business input: {str(e)}")
                conn.rollback()
                return {"status": "error", "message": str(e)}

            except Exception as e:
                log_warning(f"Unexpected issue while inserting transaction (handled response): {str(e)}")
                conn.rollback()
                return {"status": "error", "message": str(e)}

def _normalize_read_transactions_filter(value) -> ReadTransactionsFilter:
    """Normalize dynamic inputs into a valid `ReadTransactionsFilter`.
    
    Supports: ReadTransactionsFilter enum, string names (e.g., 'GENERIC'), 
    and legacy integer values (1, 2, 3, 4) for backward compatibility.
    """
    if isinstance(value, ReadTransactionsFilter):
        return value

    if isinstance(value, str):
        text = value.strip().upper()
        try:
            return ReadTransactionsFilter[text]
        except KeyError:
            raise UnavalableFilterError(f"Filter not available: {value}")

    if isinstance(value, int):
        # Legacy integer mapping for backward compatibility with Groq
        legacy_mapping = {
            1: ReadTransactionsFilter.GENERIC,
            2: ReadTransactionsFilter.LAST_DAYS,
            3: ReadTransactionsFilter.AMOUNT_GREATER_THAN,
            4: ReadTransactionsFilter.AMOUNT_LOWER_THAN,
        }
        if value in legacy_mapping:
            return legacy_mapping[value]
        raise UnavalableFilterError(f"Filter not available: {value}")

    raise UnavalableFilterError(f"Filter not available: {value}")

class ReadTransactionArgs(Transaction):
    readTransactionsFilter: Union[ReadTransactionsFilter, str, int] # Set mandatory
    type_name: Optional[str] = None # not in database, external representation of type_id
    category_name: Optional[str] = None # not in database, external representation of category_id
    last_days: Optional[int] = None # not in database, used only when readTransactionsFilter is LAST_DAYS
    source_text: None = Field(default=None, exclude=True) # Exclude source_text from the arguments, as it's not used for filtering in this tool
    description: None = Field(default=None, exclude=True) # Exclude description from the arguments, as it's not used for filtering in this tool

    @validator("source_text", pre=True, always=True)
    def block_source_text(cls, v):
        if v is not None:
            raise ValueError("source_text não pode ser usado aqui")
        return v
    
    @validator("description", pre=True, always=True)
    def block_description(cls, v):
        if v is not None:
            raise ValueError("description não pode ser usado aqui")
        return v


@tool("search_transactions", args_schema=ReadTransactionArgs)
def search_transactions(
    readTransactionsFilter: ReadTransactionsFilter,
    amount: Optional[float] = None,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    payment_method: Optional[str] = None,
    last_days: Optional[int] = None
) -> dict:
    """Busca transações com base em filtros semânticos.

    Filtros disponíveis (`readTransactionsFilter`):
    - `GENERIC`: combina qualquer subconjunto de filtros opcionais.
    - `LAST_DAYS`: exige `last_days`, em dias, jámais em minutos ou horas.
    - `AMOUNT_GREATER_THAN`: exige `amount`.
    - `AMOUNT_LOWER_THAN`: exige `amount`.

    Retorno
    -------
    dict | list[dict]
        Lista de transações ou mensagem informando ausência de resultados.
    """
    log_info("Executing read_transactions tool")

    try:
        readTransactionsFilter = _normalize_read_transactions_filter(readTransactionsFilter)
    except UnavalableFilterError as e:
        log_warning(f"Invalid filter provided for search_transactions: {str(e)}")
        return {"status": "error", "message": str(e)}

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
                        occurred_at = format_date(occurred_at)
                        filters.append("occurred_at = %s")
                        params.append(occurred_at)
                    if type_id is not None or type_name is not None:
                        resolved_type_id = _resolve_alias_id_or_raise(
                            label="type",
                            alias_dict_key="type_aliases",
                            raw_id=type_id,
                            raw_name=type_name,
                        )

                        filters.append("(type = %s)")
                        params.append(resolved_type_id)
                    if category_id is not None or category_name is not None:
                        resolved_category_id = _resolve_alias_id_or_raise(
                            label="category",
                            alias_dict_key="category_aliases",
                            raw_id=category_id,
                            raw_name=category_name,
                        )

                        filters.append("category_id = %s")
                        params.append(resolved_category_id)
                    if payment_method is not None:
                        filters.append("payment_method ILIKE %s")
                        params.append(f"%{payment_method}%")

                elif readTransactionsFilter == ReadTransactionsFilter.LAST_DAYS:
                    if last_days is None:
                        raise MissingArgumentError("Missing required argument: last_days")

                    filters.append("occurred_at >= CURRENT_DATE - (%s * INTERVAL '1 day')")
                    params.append(last_days)

                elif readTransactionsFilter == ReadTransactionsFilter.AMOUNT_GREATER_THAN:
                    if amount is None:
                        raise MissingArgumentError("Missing required argument: amount")

                    filters.append("amount > %s")
                    params.append(amount)

                elif readTransactionsFilter == ReadTransactionsFilter.AMOUNT_LOWER_THAN:
                    if amount is None:
                        raise MissingArgumentError("Missing required argument: amount")

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
                log_debug(f"SQL params: {params}")
                cur.execute(query, params)
                results = cur.fetchall()

                log_info(f"read_transactions returned {len(results)} results")
                result = [
                    dict(
                        readTransactionsFilter=readTransactionsFilter,
                        amount=row[1],
                        source_text=row[7],
                        occurred_at= format_date(row[6]),
                        type_id=row[2],
                        category_id=row[3],
                        description=row[4],
                        payment_method=row[5]
                    )
                    for row in results
                ]

                if not result:
                    log_warning("No transactions found matching the provided criteria")
                    return {"message": "No transactions found matching the criteria."}
                return result

            except (MissingArgumentError, UnavalableFilterError, UnresolvedVariableError, InvalidAliasError) as e:
                log_warning(f"search_transactions rejected due to invalid business input: {str(e)}")
                conn.rollback()
                return {"status": "error", "message": str(e)}

            except Exception as e:
                log_error(f"Unexpected issue in search_transactions (handled response): {str(e)}")
                conn.rollback()
                return {"status": "error", "message": str(e)}

# ATTENTION DEVELOPER:
# To use this tool, your database must have the following function defined:
# CREATE OR REPLACE FUNCTION get_daily_balance(p_date DATE, p_include_previous_days BOOLEAN)
# RETURNS NUMERIC AS $$
# DECLARE
#     total_balance NUMERIC;
# BEGIN

#     IF p_include_previous_days THEN
#         SELECT COALESCE(
#             SUM(
#                 CASE
#                     WHEN tt.type = 'INCOME' THEN t.amount
#                     WHEN tt.type = 'EXPENSES' THEN -t.amount
#                     ELSE 0
#                 END
#             ), 0
#         )
#         INTO total_balance
#         FROM transactions t
#         JOIN transaction_types tt ON t.type = tt.id
#         WHERE DATE(t.occurred_at) <= p_date;
#     ELSE
#         SELECT COALESCE(
#             SUM(
#                 CASE
#                     WHEN tt.type = 'INCOME' THEN t.amount
#                     WHEN tt.type = 'EXPENSES' THEN -t.amount
#                     ELSE 0
#                 END
#             ), 0
#         )
#         INTO total_balance
#         FROM transactions t
#         JOIN transaction_types tt ON t.type = tt.id
#         WHERE DATE(t.occurred_at) = p_date;
#     END IF;

#     RETURN total_balance;
# END;
# $$ LANGUAGE plpgsql;

@tool("saldo_diario")
def saldo_diario(date: str, include_previus_days: bool) -> dict:
    """Calcula o saldo diário usando a função SQL `get_daily_balance`.

    Parâmetros
    ----------
    date : str
        Data no formato `YYYY-MM-DD`.
    include_previus_days : bool
        Se `True`, acumula valores até a data; se `False`, considera apenas a data exata.
    """

    log_info("Calculating daily balance")
    try:
        date = format_date(date)
        date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        log_error(f"Invalid date format received in saldo_diario: {date}")
        return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD."}


    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT get_daily_balance(%s, %s) AS total_balance", (date, include_previus_days))
                result = cur.fetchone()
                daily_balance = float(result[0])
                    
                log_info(f"Daily balance calculated: {daily_balance}")

                return {"status": "success", "total_balance": daily_balance}
            except Exception as e:
                log_error(f"Issue calculating daily balance (handled response): {e}")
                return {"status": "error", "message": str(e)}

# ATTENTION DEVELOPER:
# To use this tool, your database must have the following function defined:
# CREATE OR REPLACE FUNCTION get_balance()
# RETURNS NUMERIC AS $$
# DECLARE
#     total_balance NUMERIC;
# BEGIN
#     SELECT COALESCE(
#         SUM(
#             CASE
#                 WHEN tt.type = 'INCOME' THEN amount
#                 WHEN tt.type = 'EXPENSES' THEN -amount
#                 ELSE 0
#             END
#         ), 0
#     ) INTO total_balance 
#     FROM transactions t
#     JOIN transaction_types tt ON t.type = tt.id;
#     RETURN total_balance;
# END;
# $$ LANGUAGE plpgsql;

@tool("saldo_total")
def saldo_total() -> dict:
    """Calcula o saldo total consolidado usando a função SQL `get_balance`."""

    log_info("Calculating total balance")

    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT get_balance() AS total_balance")
                result = cur.fetchone()
                total_balance = float(result[0] if result else 0)

                log_info(f"Total balance calculated: {total_balance}")

                return {"status": "success", "total_balance": total_balance}
            except Exception as e:
                log_error(f"Issue calculating total balance (handled response): {e}")
                return {"status": "error", "message": str(e)}

def _local_date_filter_sql(field: str = "occurred_at") -> str:
    """
    Retorna um trecho SQL para filtragem por dia local em America/Sao_Paulo.
    Ex.: (occurred_at AT TIME ZONE 'America/Sao_Paulo')::date = %s::date
    """
    return f"(({field} AT TIME ZONE 'America/Sao_Paulo')::date = %s::date)"

class UpdateTransactionArgs(BaseModel):
    id: Optional[int] = Field(
        default=None,
        description="ID da transação a atualizar. Se ausente, será feita uma busca por (match_text + date_local)."
    )
    match_text: Optional[str] = Field(
        default=None,
        description="Texto para localizar transação quando id não for informado (busca em source_text/description)."
    )
    date_local: Optional[str] = Field(
        default=None,
        description="Data local (YYYY-MM-DD) em America/Sao_Paulo; usado em conjunto com match_text quando id ausente."
    )
    amount: Optional[float] = Field(default=None, description="Novo valor.")
    type_id: Optional[int] = Field(default=None, description="Novo type_id (1/2/3).")
    type_name: Optional[str] = Field(default=None, description="Novo type_name: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="Nova categoria (id).")
    category_name: Optional[str] = Field(default=None, description="Nova categoria (nome).")
    description: Optional[str] = Field(default=None, description="Nova descrição.")
    payment_method: Optional[str] = Field(default=None, description="Novo meio de pagamento.")
    occurred_at: Optional[str] = Field(default=None, description="Novo timestamp ISO 8601.")

@tool("update_transaction", args_schema=UpdateTransactionArgs)
def update_transaction(
    id: Optional[int] = None,
    match_text: Optional[str] = None,
    date_local: Optional[str] = None,
    amount: Optional[float] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> dict:
    """
    Atualiza uma transação existente.
    Estratégias:
      - Se 'id' for informado: atualiza diretamente por ID.
      - Caso contrário: localiza a transação mais recente que combine (match_text em source_text/description)
        E (date_local em America/Sao_Paulo), então atualiza.
    Retorna: status, rows_affected, id, e o registro atualizado.
    """
    if not any([amount, type_id, type_name, category_id, category_name, description, payment_method, occurred_at]):
        return {"status": "error", "message": "Nada para atualizar: forneça pelo menos um campo (amount, type, category, description, payment_method, occurred_at)."}

    conn = Database.get_conn()
    cur = conn.cursor()
    try:
        # Resolve target_id
        target_id = id
        if target_id is None:
            if not match_text or not date_local:
                return {"status": "error", "message": "Sem 'id': informe match_text E date_local para localizar o registro."}

            # Buscar o mais recente no dia local informado que combine o texto
            cur.execute(
                f"""
                SELECT t.id
                FROM transactions t
                WHERE (t.source_text ILIKE %s OR t.description ILIKE %s)
                  AND {_local_date_filter_sql("t.occurred_at")}
                ORDER BY t.occurred_at DESC
                LIMIT 1;
                """,
                (f"%{match_text}%", f"%{match_text}%", date_local)
            )
            row = cur.fetchone()
            if not row:
                return {"status": "error", "message": "Nenhuma transação encontrada para os filtros fornecidos."}
            target_id = row[0]

        # Resolver type_id / category_id a partir de nomes, se fornecidos
        resolved_type_id = None
        if type_id is not None or type_name is not None:
            resolved_type_id = ALIAS_SERVICE.resolve_type_id(type_name=type_name, type_id=type_id)
            if resolved_type_id is None:
                return {"status": "error", "message": "Tipo inválido: informe type_id ou type_name válido."}

        resolved_category_id = None
        if category_id is not None or category_name is not None:
            resolved_category_id = ALIAS_SERVICE.resolve_category_id(category_id=category_id, category_name=category_name)
            if resolved_category_id is None:
                return {"status": "error", "message": "Categoria inválida: informe category_id ou category_name válido."}

        # Montar SET dinâmico
        sets = []
        params: List[object] = []
        if amount is not None:
            sets.append("amount = %s")
            params.append(amount)
        if resolved_type_id is not None:
            sets.append("type = %s")
            params.append(resolved_type_id)
        if resolved_category_id is not None:
            sets.append("category_id = %s")
            params.append(resolved_category_id)
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if payment_method is not None:
            sets.append("payment_method = %s")
            params.append(payment_method)
        if occurred_at is not None:
            sets.append("occurred_at = %s::timestamptz")
            params.append(occurred_at)

        if not sets:
            return {"status": "error", "message": "Nenhum campo válido para atualizar."}

        params.append(target_id)

        cur.execute(
            f"UPDATE transactions SET {', '.join(sets)} WHERE id = %s;",
            params
        )
        rows_affected = cur.rowcount
        conn.commit()

        # Retornar o registro atualizado
        cur.execute(
            """
            SELECT
              t.id, t.occurred_at, t.amount, tt.type AS type_name,
              c.name AS category_name, t.description, t.payment_method, t.source_text
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.id = %s;
            """,
            (target_id,)
        )
        r = cur.fetchone()
        updated = None
        if r:
            updated = {
                "id": r[0],
                "occurred_at": str(r[1]),
                "amount": float(r[2]),
                "type": r[3],
                "category": r[4],
                "description": r[5],
                "payment_method": r[6],
                "source_text": r[7],
            }

        return {
            "status": "ok",
            "rows_affected": rows_affected,
            "id": target_id,
            "updated": updated
        }

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# Define tools:
TOOLS = [add_transaction, search_transactions, saldo_total, saldo_diario, update_transaction]