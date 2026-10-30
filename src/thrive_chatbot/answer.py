"""Optional step: have a language model write a short answer from the retrieved articles only.

Off by default (USE_LLM=false), so v1 needs no API key. Turn it on in .env once the cost/ownership
question is settled. Install the provider package you need, e.g. `pip install langchain-anthropic`.
"""
from . import config
from .search import Hit

SYSTEM_PROMPT = (
    "You help visitors of the THRIVE Central Florida literature library. Answer ONLY from the numbered "
    "articles provided. Keep it to 2-4 sentences, in plain language. Cite articles like [1] or [2]. "
    "If the articles do not answer the question, say you could not find that in the library and do not "
    "use outside knowledge. Never invent articles, links, or statistics."
)


def build_context(hits: list[Hit]) -> str:
    blocks = []
    for n, h in enumerate(hits, 1):
        a = h.article
        parts = [f"[{n}] {a.title}", f"Main idea: {a.main_idea}"]
        if a.problems:
            parts.append(f"Problems: {a.problems}")
        if a.solutions:
            parts.append(f"Solutions: {a.solutions}")
        if a.implement:
            parts.append(f"How to apply: {a.implement}")
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def build_messages(question: str, hits: list[Hit]) -> list[tuple[str, str]]:
    return [
        ("system", SYSTEM_PROMPT),
        ("human", f"Articles:\n\n{build_context(hits)}\n\nQuestion: {question}"),
    ]


def _load_model(spec: str):
    provider, _, name = spec.partition(":")
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=name, temperature=0, max_tokens=400)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=name, temperature=0, max_tokens=400)
    raise ValueError("LLM_MODEL must look like 'anthropic:<model>' or 'openai:<model>'.")


def generate_answer(question: str, hits: list[Hit]) -> str:
    if not config.LLM_MODEL:
        raise RuntimeError("Set LLM_MODEL in .env to use LLM answers.")
    if not hits:
        return "I couldn't find that in the library."
    model = _load_model(config.LLM_MODEL)
    return model.invoke(build_messages(question, hits)).content
