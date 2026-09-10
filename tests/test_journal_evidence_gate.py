from iot_poc.journal_evidence_gate import (
    action_retrieval_query,
    checker_keeps_action,
    deterministic_eligibility,
    exact_paired_test,
    fallback_candidates,
    fallback_action_for,
    fallback_retrieval_query,
)


def sample_item(action: str = "RATE_LIMIT", route: str = "plan") -> dict:
    return {
        "predicted_family": "DDoS",
        "route": route,
        "action": action,
        "approval_required": action == "RATE_LIMIT",
        "evidence_refs": ["doc-1"],
        "cited_evidence": [{"chunk_id": "doc-1"}],
    }


def test_action_query_contains_family_action_protocol_and_observation_terms() -> None:
    alert = {
        "detector": {"predicted_family": "DDoS"},
        "observations": {"TCP": 1, "HTTP": 1, "Rate": 1234, "syn_count": 10},
    }
    query = action_retrieval_query(alert, "RATE_LIMIT")
    assert "DDoS" in query
    assert "RATE_LIMIT" in query
    assert "TCP" in query and "HTTP" in query
    assert "packet rate" in query and "SYN" in query


def test_deterministic_filter_checks_ids_and_family_compatibility() -> None:
    valid, reasons = deterministic_eligibility(sample_item())
    assert valid and not reasons

    bad_id = sample_item()
    bad_id["evidence_refs"] = ["not-retrieved"]
    valid, reasons = deterministic_eligibility(bad_id)
    assert not valid
    assert any("outside" in reason for reason in reasons)

    incompatible = sample_item("RESTRICT_EGRESS")
    valid, reasons = deterministic_eligibility(incompatible)
    assert not valid
    assert any("not allowed" in reason for reason in reasons)


def test_strict_gate_keeps_supported_nondisruptive_and_rejects_weak_disruption() -> None:
    disruptive = sample_item()
    keep, _ = checker_keeps_action(disruptive, "directly_supported", "strict")
    assert keep
    keep, _ = checker_keeps_action(disruptive, "generally_supported", "strict")
    assert not keep
    keep, _ = checker_keeps_action(disruptive, "generally_supported", "review_queue")
    assert keep

    nondisruptive = sample_item("CAPTURE_TRAFFIC")
    keep, _ = checker_keeps_action(nondisruptive, "generally_supported", "strict")
    assert keep
    keep, _ = checker_keeps_action(nondisruptive, "unsupported", "strict")
    assert not keep


def test_fallback_depends_on_route_and_family_policy() -> None:
    def record(route: str, family: str) -> dict:
        return {
            "normalized_intent": {"route": route},
            "alert": {"detector": {"predicted_family": family}},
        }

    assert fallback_action_for(record("monitor", "Benign")) == "MONITOR"
    assert fallback_action_for(record("escalate", "DDoS")) == "NOTIFY_OPERATOR"
    assert fallback_action_for(record("plan", "Recon")) == "CAPTURE_TRAFFIC"
    assert fallback_action_for(record("plan", "BruteForce")) == "NOTIFY_OPERATOR"
    assert fallback_candidates(record("escalate", "DDoS")) == [
        "CAPTURE_TRAFFIC",
        "MONITOR",
        "NOTIFY_OPERATOR",
    ]
    assert fallback_candidates(record("plan", "BruteForce")) == ["NOTIFY_OPERATOR"]


def test_fallback_query_prioritizes_the_action_terms() -> None:
    alert = {
        "detector": {"predicted_family": "Web"},
        "observations": {"TCP": 1, "HTTP": 1},
    }
    query = fallback_retrieval_query(alert, "NOTIFY_OPERATOR")
    assert query.count("incident notification") >= 3
    assert "Web" in query and "HTTP" in query


def test_exact_paired_test_counts_improvement_and_regression() -> None:
    before = {"a": False, "b": False, "c": True, "d": True}
    after = {"a": True, "b": False, "c": False, "d": True}
    result = exact_paired_test(before, after)
    assert result["improved_cases"] == 1
    assert result["worsened_cases"] == 1
    assert result["discordant_cases"] == 2
