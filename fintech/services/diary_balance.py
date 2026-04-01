# ATTENTION DEVELOPER:
# To use this file, your database must have the following function defined:
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
#                     WHEN tt.type = 'EXPENSE' THEN -t.amount
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
#                     WHEN tt.type = 'EXPENSE' THEN -t.amount
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

from langchain.tools import tool
from datetime import datetime
from ..logger import log_error, log_debug, log_info, log_warning
from .utils import Database


@tool("saldo_diario")
def saldo_diario(date: str, include_previus_days: bool) -> dict:
    """Retorna o saldo diário calculado a partir das transações financeiras no banco de dados Postgres."""

    log_info("Calculating daily balance")
    try:
        date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        log_error(f"Invalid date format: {date}")
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
                log_error(f"Error calculating daily balance: {e}")
                return {"status": "error", "message": str(e)}