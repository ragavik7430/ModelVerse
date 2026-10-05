from __future__ import annotations

from typing import Any, Dict


def explain_recommendation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    problem_type = state.get("problem_type", "unknown")
    dataset_characteristics = state.get("dataset_characteristics") or {}
    candidate_algorithms = state.get("candidate_algorithms") or []
    suggested_preprocessing = state.get("preprocessing_steps") or []
    warnings = state.get("warnings") or []
    recommendation = state.get("recommended_pipeline") or "Information insufficient"
    rationale = state.get("rationale") or "No rationale available."
    confidence = state.get("confidence") or 0.0

    row_count = dataset_characteristics.get("row_count") or 0
    column_count = dataset_characteristics.get("column_count") or 0
    missing_total = sum(
        int(value)
        for value in (dataset_characteristics.get("missing_values") or {}).values()
        if isinstance(value, (int, float))
    )
    quality_status = dataset_characteristics.get("quality_status") or "unknown"

    explanation_lines = [
        f"Detected problem type: {problem_type}.",
        f"Dataset profile: {row_count} rows and {column_count} columns. "
        f"Missing values observed across the dataset: {missing_total} cells.",
        f"Candidate algorithms: {', '.join(candidate_algorithms) if candidate_algorithms else 'Not enough information to infer candidates.'}",
        f"Recommended pipeline: {recommendation}",
        f"Preprocessing expected: {', '.join(suggested_preprocessing) if suggested_preprocessing else 'No specific preprocessing steps flagged.'}",
        f"Confidence: {confidence:.2f}.",
        f"Quality status: {quality_status}.",
        f"User review: Confirm the target variable, feature definitions, and the final pipeline before moving forward.",
    ]

    explanation = " ".join(explanation_lines)
    if warnings:
        explanation = f"{explanation} Warnings: {'; '.join(warnings)}."

    return {
        "explanation": explanation,
        "rationale": rationale,
    }
