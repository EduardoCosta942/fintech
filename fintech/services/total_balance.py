# ATTENTION DEVELOPER:
# To use this file, your database must have the following function defined:
# CREATE OR REPLACE FUNCTION get_balance()
# RETURNS NUMERIC AS $$
# DECLARE
#     total_balance NUMERIC;
# BEGIN
#     SELECT COALESCE(
#         SUM(
#             CASE
#                 WHEN tt.type = 'INCOME' THEN amount
#                 WHEN tt.type = 'EXPENSE' THEN -amount
#                 ELSE 0
#             END
#         ), 0
#     ) INTO total_balance 
#     FROM transactions t
#     JOIN transaction_types tt ON t.type = tt.id;
#     RETURN total_balance;
# END;
# $$ LANGUAGE plpgsql;

# SELECT get_balance() AS total_balance;

from langchain.tools import tool
from ..logger import log_error, log_debug, log_info, log_warning
from .utils import Database

@tool("saldo_total")
def saldo_total() -> dict:
    """Retorna o saldo total calculado a partir das transações financeiras no banco de dados Postgres."""

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
                log_error(f"Error calculating total balance: {e}")
                return {"status": "error", "message": str(e)}