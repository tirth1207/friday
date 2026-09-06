from core.orchestrator_structured import _clean_model_answer, _extract_repository_target


def test_explicit_repository_in_message_overrides_selected_repository():
    assert _extract_repository_target(
        "Repository tirth1207/DevNest explain this project",
        "explain this project",
        selected_repository="tirth1207/Orbit",
    ) == "tirth1207/DevNest"


def test_selected_repository_is_used_when_message_has_no_explicit_target():
    assert _extract_repository_target(
        "what is this project and how it works",
        "what is this project and how it works",
        selected_repository="tirth1207/DevNest",
    ) == "tirth1207/DevNest"


def test_model_answer_does_not_expose_thinking_wrapper_or_internal_preamble():
    raw = """We need to produce a complete explanation from the evidence.\n\n## Overview\nDevNest is a project."""
    assert _clean_model_answer(raw).startswith("## Overview")


def test_model_answer_removes_think_tags():
    raw = "<think>internal reasoning</think>\n\n## Overview\nFinal answer."
    assert _clean_model_answer(raw) == "## Overview\nFinal answer."
