from .add_transaction import add_transaction
from .read_transactions import search_transactions
from ..agent import AgentSingleton
from ..exceptions import AgentRequestError
from ..logger import log_error, log_debug, log_info

_AGENT_SINGLETON = None
_TOOLS = [add_transaction, search_transactions]

def _get_agent_singleton():
    global _AGENT_SINGLETON

    if _AGENT_SINGLETON is None:
        log_info("Initializing AgentFactory instance")
        _AGENT_SINGLETON = AgentSingleton(_TOOLS).agent
        return
    
    log_debug("Reusing existing AgentFactory instance")

def request(user_prompt: str):
    log_info("Processing user request")

    global _AGENT_SINGLETON
    _get_agent_singleton()

    try:
        log_debug("Agent created, invoking with user prompt")

        response = _AGENT_SINGLETON.invoke(
            {"messages": [{"role": "human", "content": user_prompt}]},
            config={"configurable": {"thread_id": "develop"}, "recursion_limit": 8}
        )

        log_info("Request processed successfully")

        return response

    except Exception as e:
        log_error(str(e))
        raise AgentRequestError(f"An error occurred while processing the request: {str(e)}")