import psycopg2
from typing import Optional
from langchain.tools import tool
from ..env_loader import get_env_variable
from ..models import Transaction

TYPE_ALIASES = {}
CATEGORIES_ALIASES = {}
INVERSE_TYPE_ALIASES = {}
INVERSE_CATEGORY_ALIASES = {}


def _get_conn():
    return psycopg2.connect(get_env_variable("DATABASE_URL"), connect_timeout=5)

# Define constants:
def _define_constants() -> None:
    type_aliases = {}
    category_aliases = {}
    inverse_type_aliases = {}
    inverse_category_aliases = {}

    with _get_conn() as conn:
        with conn.cursor() as cur:
            # transaction_types
            cur.execute("SELECT id, type FROM transaction_types;")
            for row in cur.fetchall():
                type_aliases[row[0]] = row[1]
                inverse_type_aliases[row[1]] = row[0]

            # Categories
            cur.execute("SELECT id, name FROM categories;")
            for row in cur.fetchall():
                category_aliases[row[0]] = row[1]
                inverse_category_aliases[row[1]] = row[0]

            # Update the global constants
            global TYPE_ALIASES, CATEGORIES_ALIASES, INVERSE_TYPE_ALIASES, INVERSE_CATEGORY_ALIASES
            TYPE_ALIASES = type_aliases
            CATEGORIES_ALIASES = category_aliases
            INVERSE_TYPE_ALIASES = inverse_type_aliases
            INVERSE_CATEGORY_ALIASES = inverse_category_aliases



#Garante que o campo type da tabela transactions receba um id válido
def _resolve_type_id(type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
    if not TYPE_ALIASES:
        _define_constants()
    if TYPE_ALIASES.get(type_id):
        return type_id
    if type_name and INVERSE_TYPE_ALIASES.get(type_name):
        return INVERSE_TYPE_ALIASES[type_name]
    return None

# Garante que o campo category_id da tabela transactions receba um id válido
def _resolve_category_id(category_id: int) -> Optional[int]:
    if not CATEGORIES_ALIASES:
        _define_constants()
    if CATEGORIES_ALIASES.get(category_id):
        return category_id
    return None

# Tool: add_transaction
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
    """Insere uma transação financeira no banco de dados Postgres.""" # docstring obrigatório da @tools do langchain (estranho, mas legal né?)
    with _get_conn() as conn:
        with conn.cursor() as cur:
            try:
                resolved_type_id = _resolve_type_id(type_id, type_name)
                print(f"\033[32mTesting type: Name: {type_name}, ID: {type_id}\033[0m")
                if not resolved_type_id:
                    string = ""
                    for key, value in TYPE_ALIASES.items():
                        string += f"{value} (id: {key}); "

                    error = ValueError({"status": "error", "message": f"Tipo inválido (use type_name ou type_id: {string.rstrip('; ')})."})
                    print(f"\033[91mError:{error}\033[0m")
                    raise error

                resolved_category_id = _resolve_category_id(category_id)
                print(f"\033[32mTesting category: ID: {category_id}\033[0m")
                if not resolved_category_id:
                    string = ""
                    for key, value in CATEGORIES_ALIASES.items():
                        string += f"{value} (id: {key}); "

                    error = ValueError({"status": "error", "message": f"Categoria inválida (use category_id: {string.rstrip('; ')})."})
                    print(f"\033[91mError: {error}\033[0m")
                    raise error

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
                return {"status": "ok", "id": new_id, "occurred_at": str(occurred)}

            except Exception as e:
                conn.rollback()
                return {"status": "error", "message": str(e)}