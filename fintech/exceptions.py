class ModelUnavailableError(Exception):
    def __init__(self, message="Model is unavailable"):
        self.message = message
        super().__init__(self.message)

class AgentRequestError(Exception):
    def __init__(self, message="Model is unavailable"):
        self.message = message
        super().__init__(self.message)

class EnvNotFoundError(Exception):
    def __init__(self, message="Environment variable not found"):
        self.message = message
        super().__init__(self.message)

class UnavalableFilterError(Exception):
    def __init__(self, message="Requested filter is unavailable for this operation"):
        self.message = message
        super().__init__(self.message)

class MissingArgumentError(Exception):
    def __init__(self, message="Missing required argument"):
        self.message = message
        super().__init__(self.message)

class UnresolvedVariableError(Exception):
    def __init__(self, message="Unresolved variable in the input"):
        self.message = message
        super().__init__(self.message)