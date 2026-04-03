from ..agent import AgentSingleton
from ..exceptions import AgentRequestError
from ..logger import log_debug, log_info, log_error
from .pg_tools import TOOLS

_AGENT_SINGLETON = None

def _get_agent_singleton():
    global _AGENT_SINGLETON

    if _AGENT_SINGLETON is None:
        log_info("Initializing AgentFactory instance")
        _AGENT_SINGLETON = AgentSingleton(TOOLS).agent
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
        log_error(f"Request failed with handled exception: {str(e)}")
        raise AgentRequestError(f"An error occurred while processing the request: {str(e)}")