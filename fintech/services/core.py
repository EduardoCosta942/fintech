from .add_transaction import add_transaction
from ..agent import build_agent
from ..exceptions import AgentRequestError

_AGENT = None


def _get_agent():
    global _AGENT
    if _AGENT is None:
        _AGENT = build_agent(tools=[add_transaction])
    return _AGENT

def request(user_prompt: str):
    try:
        response = _get_agent().invoke(
            {"messages": [{"role": "human", "content": user_prompt}]},
            config={"configurable": {"thread_id": "develop"}, "recursion_limit": 8}
        )
        return response
    except Exception as e:
        raise AgentRequestError(f"An error occurred while processing the request: {str(e)}")