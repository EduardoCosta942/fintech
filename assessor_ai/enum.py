from enum import Enum, auto

class Environment(Enum):
    DEVELOPMENT = auto()
    PRODUCTION = auto()

class ReadTransactionsFilter(str, Enum):
    GENERIC = "GENERIC"
    LAST_DAYS = "LAST_DAYS"
    AMOUNT_GREATER_THAN = "AMOUNT_GREATER_THAN"
    AMOUNT_LOWER_THAN = "AMOUNT_LOWER_THAN"