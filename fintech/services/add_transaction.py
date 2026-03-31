from typing import Optional
from langchain.tools import tool
from ..logger import log_error, log_debug, log_info, log_warning
from ..models import Transaction
from .utils import ALIASES, ALIAS_SERVICE, Database

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

    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            try:
                resolved_type_id = ALIAS_SERVICE.resolve_type_id(type_id, type_name)

                if not resolved_type_id:
                    string = ""
                    for key, value in ALIASES["type_aliases"].items():
                        string += f"{value} (id: {key}); "

                    error = ValueError({
                        "status": "error",
                        "message": f"Invalid type (use type_name or type_id: {string.rstrip('; ')})"
                    })

                    log_warning("Transaction rejected due to invalid type")
                    raise error

                resolved_category_id = ALIAS_SERVICE.resolve_category_id(category_id)

                if not resolved_category_id:
                    string = ""
                    for key, value in ALIASES["category_aliases"].items():
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