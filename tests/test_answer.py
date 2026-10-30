from thrive_chatbot import answer
from thrive_chatbot.data import Article
from thrive_chatbot.search import Hit


def hit(title: str, **kw) -> Hit:
    a = Article(id=title, title=title, authors="", link="", main_idea="Idea", problems="", solutions="",
                implement="", **kw)
    return Hit(a, 0.5, "Main idea", "Idea", ["semantic"])


def test_context_numbers_articles_and_skips_empty_fields():
    ctx = answer.build_context([hit("First"), hit("Second")])
    assert "[1] First" in ctx and "[2] Second" in ctx
    assert "Problems:" not in ctx


def test_messages_contain_grounding_rules_and_question():
    msgs = answer.build_messages("What about housing?", [hit("First")])
    assert msgs[0][0] == "system" and "ONLY" in msgs[0][1]
    assert "What about housing?" in msgs[1][1]


def test_no_hits_does_not_call_a_model(monkeypatch):
    monkeypatch.setattr(answer.config, "LLM_MODEL", "anthropic:x")
    assert "couldn't find" in answer.generate_answer("anything", [])
