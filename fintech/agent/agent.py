from ..env_loader import get_ai_config
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from ..exceptions import ModelUnavailableError
from langchain.agents import create_agent
from .system_prompt import build_system_prompt
from langgraph.checkpoint.memory import MemorySaver


# Build llm with fallbacks
def _get_llm():
    global _GEMINI_KEY, _GROQ_KEY, _GEMINI_MODEL, _GROQ_MODEL
    _GEMINI_KEY, _GROQ_KEY, _GEMINI_MODEL, _GROQ_MODEL = get_ai_config()

    llm = None

    def _get_gemini_llm():
            return ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL,
                temperature=0.7,
                top_p=0.95,
            )

    def _get_groq_llm():
        return ChatGroq(
            model=_GROQ_MODEL,
            temperature=1,
            top_p=0.95
        )

    if _GEMINI_KEY and _GROQ_KEY and _GEMINI_MODEL and _GROQ_MODEL:
        llm = _get_gemini_llm().with_fallbacks(
            [
                _get_groq_llm()
            ]
        )
    elif _GEMINI_KEY and _GEMINI_MODEL:
        llm = _get_gemini_llm()
    elif _GROQ_KEY and _GROQ_MODEL:
        llm = _get_groq_llm()
    else:
         raise ModelUnavailableError()
    return llm


def build_agent(tools: list | None = None):
    if tools is None:
        tools = []
    return create_agent(
        model=_get_llm(),
        tools=tools,
        system_prompt=build_system_prompt(),
        checkpointer=MemorySaver()
    )
    