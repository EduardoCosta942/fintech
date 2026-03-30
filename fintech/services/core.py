from .add_transaction import add_transaction
from ..agent import AgentFactory
from ..exceptions import AgentRequestError
from ..logger import log_error, log_debug, log_info

_AGENT_FACTORY = None


def _get_agent_factory():
    global _AGENT_FACTORY

    if _AGENT_FACTORY is None:
        log_info("Initializing AgentFactory instance")
        _AGENT_FACTORY = AgentFactory()
    else:
        log_debug("Reusing existing AgentFactory instance")

    return _AGENT_FACTORY


def request(user_prompt: str):
    log_info("Processing user request")

    try:
        agent = _get_agent_factory().create(tools=[add_transaction])

        log_debug("Agent created, invoking with user prompt")

        response = agent.invoke(
            {"messages": [{"role": "human", "content": user_prompt}]},
            config={"configurable": {"thread_id": "develop"}, "recursion_limit": 8}
        )

        log_info("Request processed successfully")

        return response

    except Exception as e:
        log_error(str(e))
        raise AgentRequestError(f"An error occurred while processing the request: {str(e)}")