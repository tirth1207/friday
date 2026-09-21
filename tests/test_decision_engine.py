from core.decision_engine import DecisionEngine, RiskLevel


def test_safe_action_is_allowed():
    decision = DecisionEngine().decide("read")
    assert decision.allowed
    assert not decision.requires_confirmation
    assert decision.risk == RiskLevel.SAFE


def test_mutation_requires_approval():
    decision = DecisionEngine().decide("push")
    assert not decision.allowed
    assert decision.requires_confirmation
    assert decision.risk == RiskLevel.MEDIUM

    approved = DecisionEngine().decide("push", approved=True)
    assert approved.allowed


def test_unknown_action_is_denied():
    decision = DecisionEngine().decide("launch_spacecraft")
    assert not decision.allowed
