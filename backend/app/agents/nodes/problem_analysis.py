from __future__ import annotations

from typing import Any, Dict


def _normalized_text(value: str | None) -> str:
    return (value or "").strip().lower()


def analyze_problem_node(state: Dict[str, Any]) -> Dict[str, Any]:
    problem_statement = state.get("problem_statement", "")
    objective = state.get("objective", "")
    combined_text = f"{problem_statement} {objective}".strip()
    normalized = _normalized_text(combined_text)

    classification_keywords = (
        "classify",
        "classification",
        "predict class",
        "spam",
        "fraud",
        "churn",
        "label",
        "outcome",
        "disease",
        "customer",
        "will buy",
        "will cancel",
        "risk",
        "default",
    )
    regression_keywords = (
        "regression",
        "forecast",
        "predict value",
        "estimate",
        "sales",
        "revenue",
        "price",
        "cost",
        "temperature",
        "demand",
        "time series",
        "continuous",
    )
    clustering_keywords = (
        "cluster",
        "segment",
        "group",
        "similarity",
        "unsupervised",
        "pattern",
        "discover",
    )

    if any(keyword in normalized for keyword in clustering_keywords):
        problem_type = "clustering"
    elif any(keyword in normalized for keyword in regression_keywords):
        problem_type = "regression"
    elif any(keyword in normalized for keyword in classification_keywords):
        problem_type = "classification"
    else:
        problem_type = "unknown"

    target_candidate = None
    if problem_type != "unknown":
        target_tokens = ["target", "label", "class", "outcome", "response", "y_value"]
        for token in target_tokens:
            if token in normalized:
                target_candidate = token
                break

    warnings: list[str] = []
    if target_candidate is None:
        warnings.append("Target variable could not be determined automatically.")
    if problem_type == "unknown":
        warnings.append("Problem type is uncertain; additional project context is needed.")

    confidence = 0.9 if problem_type != "unknown" else 0.35
    if target_candidate is not None:
        confidence = min(confidence + 0.05, 0.99)

    rationale = (
        f"The project text suggests a {problem_type} problem with a confidence of {confidence:.2f}. "
        "The system avoided guessing a target variable when the prompt did not clearly define one."
    )

    return {
        "problem_type": problem_type,
        "target_candidate": target_candidate,
        "confidence": confidence,
        "warnings": warnings,
        "rationale": rationale,
    }
