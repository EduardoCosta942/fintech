import psycopg2
from typing import Optional
from langchain.tools import tool

from ..logger import log_error, log_debug, log_info, log_warning
from ..env_loader import get_env_variable
from ..models import Transaction

TYPE_ALIASES = {}
CATEGORIES_ALIASES = {}
INVERSE_TYPE_ALIASES = {}
INVERSE_CATEGORY_ALIASES = {}


def _get_conn():
    log_debug("Opening database connection")
    return psycopg2.connect(get_env_variable("DATABASE_URL"), connect_timeout=5)


def _define_constants() -> None:
    log_debug("Loading type and category aliases from database")

    type_aliases = {}
    category_aliases = {}
    inverse_type_aliases = {}
    inverse_category_aliases = {}

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, type FROM transaction_types;")
            for row in cur.fetchall():
                type_aliases[row[0]] = row[1]
                inverse_type_aliases[row[1]] = row[0]

            cur.execute("SELECT id, name FROM categories;")
            for row in cur.fetchall():
                category_aliases[row[0]] = row[1]
                inverse_category_aliases[row[1]] = row[0]

            global TYPE_ALIASES, CATEGORIES_ALIASES, INVERSE_TYPE_ALIASES, INVERSE_CATEGORY_ALIASES
            TYPE_ALIASES = type_aliases
            CATEGORIES_ALIASES = category_aliases
            INVERSE_TYPE_ALIASES = inverse_type_aliases
            INVERSE_CATEGORY_ALIASES = inverse_category_aliases

    log_info("Aliases loaded successfully")


def _resolve_type_id(type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
    if not TYPE_ALIASES:
        log_debug("TYPE_ALIASES empty, loading constants")
        _define_constants()

    if TYPE_ALIASES.get(type_id):
        log_debug(f"Resolved type_id directly: {type_id}")
        return type_id

    if type_name and INVERSE_TYPE_ALIASES.get(type_name):
        resolved = INVERSE_TYPE_ALIASES[type_name]
        log_debug(f"Resolved type_name '{type_name}' to id {resolved}")
        return resolved

    log_warning("Invalid transaction type provided")
    return None


def _resolve_category_id(category_id: int) -> Optional[int]:
    if not CATEGORIES_ALIASES:
        log_debug("CATEGORIES_ALIASES empty, loading constants")
        _define_constants()

    if CATEGORIES_ALIASES.get(category_id):
        log_debug(f"Resolved category_id: {category_id}")
        return category_id

    log_warning("Invalid category_id provided")
    return None


@tool("add_transaction", args_schema=Transaction)
def add_transaction(
    amount: float,
    source_text: str,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
    """Insere uma transação financeira no banco de dados Postgres."""

    log_info("Starting transaction insertion")

    with _get_conn() as conn:
        with conn.cursor() as cur:
            try:
                resolved_type_id = _resolve_type_id(type_id, type_name)

                if not resolved_type_id:
                    string = ""
                    for key, value in TYPE_ALIASES.items():
                        string += f"{value} (id: {key}); "

                    error = ValueError({
                        "status": "error",
                        "message": f"Invalid type (use type_name or type_id: {string.rstrip('; ')})"
                    })

                    log_warning("Transaction rejected due to invalid type")
                    raise error

                resolved_category_id = _resolve_category_id(category_id)

                if not resolved_category_id:
                    string = ""
                    for key, value in CATEGORIES_ALIASES.items():
                        string += f"{value} (id: {key}); "

                    error = ValueError({
                        "status": "error",
                        "message": f"Invalid category (use category_id: {string.rstrip('; ')})"
                    })

                    log_warning("Transaction rejected due to invalid category")
                    raise error

                log_debug("Executing INSERT into transactions")

                if occurred_at:
                    cur.execute(
                        """
                        INSERT INTO transactions
                            (amount, type, category_id, description, payment_method, occurred_at, source_text)
                        VALUES
                            (%s, %s, %s, %s, %s, %s::timestamptz, %s)
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

            except Exception as e:
                log_error(str(e))
                conn.rollback()
                return {"status": "error", "message": str(e)}