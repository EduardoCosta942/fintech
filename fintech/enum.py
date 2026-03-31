from enum import Enum, auto

class Environment(Enum):
    DEVELOPMENT = auto()
    PRODUCTION = auto()

class ReadTransactionsFilter(Enum):
    GENERIC = 1
    LAST_DAYS = 2
    AMOUNT_GREATER_THAN = 3
    AMOUNT_LOWER_THAN = 4
    DESCRIPTION_OR_SOURCE_TEXT_CONTAINS = 5