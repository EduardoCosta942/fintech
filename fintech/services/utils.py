import psycopg2
from typing import Optional, Dict
from ..env_loader import get_env_variable
from ..logger import log_debug, log_info, log_warning


class Database:
    @staticmethod
    def get_conn():
        log_debug("Opening database connection")
        return psycopg2.connect(get_env_variable("DATABASE_URL"), connect_timeout=5)


class AliasRepository:
    @staticmethod
    def load_aliases() -> Dict[str, dict]:
        log_debug("Loading aliases from database")

        type_aliases = {}
        inverse_type_aliases = {}
        category_aliases = {}
        inverse_category_aliases = {}

        with Database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, type FROM transaction_types;")
                for _id, name in cur.fetchall():
                    type_aliases[_id] = name
                    inverse_type_aliases[name] = _id

                cur.execute("SELECT id, name FROM categories;")
                for _id, name in cur.fetchall():
                    category_aliases[_id] = name
                    inverse_category_aliases[name] = _id

        log_info("Aliases loaded successfully")

        return {
            "type_aliases": type_aliases,
            "inverse_type_aliases": inverse_type_aliases,
            "category_aliases": category_aliases,
            "inverse_category_aliases": inverse_category_aliases,
        }


class AliasService:
    def __init__(self, data: Dict[str, dict] = AliasRepository.load_aliases()):
        self.type_aliases = data["type_aliases"]
        self.inverse_type_aliases = data["inverse_type_aliases"]
        self.category_aliases = data["category_aliases"]
        self.inverse_category_aliases = data["inverse_category_aliases"]

    def resolve_type_id(self, type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
        if type_id in self.type_aliases:
            log_debug(f"Resolved type_id directly: {type_id}")
            return type_id

        if type_name in self.inverse_type_aliases:
            resolved = self.inverse_type_aliases[type_name]
            log_debug(f"Resolved type_name '{type_name}' to id {resolved}")
            return resolved

        log_warning("Invalid transaction type provided")
        return None

    def resolve_category_id(self, category_id: int) -> Optional[int]:
        if category_id in self.category_aliases:
            log_debug(f"Resolved category_id: {category_id}")
            return category_id

        log_warning("Invalid category_id provided")
        return None

ALIASES = AliasRepository.load_aliases()
ALIAS_SERVICE = AliasService()