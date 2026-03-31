from ..env_loader import get_ai_config
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from ..exceptions import ModelUnavailableError
from langchain.agents import create_agent
from .system_prompt import build_system_prompt
from langgraph.checkpoint.memory import MemorySaver

from ..logger import log_info, log_debug, log_warning, log_error


class AgentSingleton:
    def __init__(self, tools=[]):
        log_debug("Initializing AgentSingleton")

        self._gemini_key, self._groq_key, self._gemini_model, self._groq_model = get_ai_config()

        log_debug(
            f"Config loaded | Gemini: {bool(self._gemini_key)} | Groq: {bool(self._groq_key)}"
        )

        self._tools = tools
        self._llm = self._get_llm()
        self._memory_saver = MemorySaver()
        self.agent = self._create(self._tools)

    def _get_llm(self):
        log_debug("Selecting available LLM")

        _llm = None

        def _get_gemini_llm():
            log_info("Creating Gemini instance")
            return ChatGoogleGenerativeAI(
                model=self._gemini_model,
                api_key=self._gemini_key,
                temperature=0.7,
                top_p=0.95,
            )

        def _get_groq_llm():
            log_info("Creating Groq instance")
            return ChatGroq(
                model=self._groq_model,
                api_key=self._groq_key,
                temperature=1,
                top_p=0.95
            )

        if self._gemini_key and self._groq_key and self._gemini_model and self._groq_model:
            log_info("Using Gemini with Groq fallback")
            _llm = _get_gemini_llm().with_fallbacks(
                [
                    _get_groq_llm()
                ]
            )
        elif self._gemini_key and self._gemini_model:
            log_warning("Only Gemini available, no fallback configured")
            _llm = _get_gemini_llm()
        elif self._groq_key and self._groq_model:
            log_warning("Only Groq available, no fallback configured")
            _llm = _get_groq_llm()
        else:
            log_error(str(ModelUnavailableError()))
            raise ModelUnavailableError()

        log_debug("LLM successfully selected")
        return _llm

    def _create(self, tools):
        log_debug("Creating agent")

        tools = tools if tools is not None else []

        log_debug(f"Tools count: {len(tools)}")

        agent = create_agent(
            model=self._llm,
            tools=tools,
            system_prompt=build_system_prompt(),
            checkpointer=self._memory_saver
        )

        log_info("Agent created successfully")
        return agent