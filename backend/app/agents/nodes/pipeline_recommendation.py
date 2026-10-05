from __future__ import annotations

from typing import Any, Dict


def _has_missing_values(dataset_summary: Dict[str, Any]) -> bool:
    missing_values = dataset_summary.get("missing_values") or {}
    return any(int(value) > 0 for value in missing_values.values() if isinstance(value, (int, float)))


def _has_duplicate_rows(dataset_summary: Dict[str, Any]) -> bool:
    return int((dataset_summary or {}).get("duplicate_rows") or 0) > 0


def _has_categorical_columns(dataset_summary: Dict[str, Any]) -> bool:
    categorical_columns = dataset_summary.get("categorical_columns") or []
    return bool(categorical_columns)


def recommend_pipeline_node(state: Dict[str, Any]) -> Dict[str, Any]:
    problem_type = state.get("problem_type", "unknown")
    dataset_summary = state.get("dataset_summary") or {}
    warnings = list(state.get("warnings") or [])

    recommended_pipeline = "More information is required before choosing a pipeline."
    candidate_algorithms: list[str] = []
    preprocessing_steps: list[str] = []

    if problem_type == "classification":
        candidate_algorithms = ["Logistic Regression", "Random Forest", "Gradient Boosting"]
        recommended_pipeline = "Classification baseline with preprocessing, validation, and model comparison."
        preprocessing_steps = [
            "Validate the target variable and label definition.",
            "Encode categorical feature values.",
            "Split the data into training and validation sets.",
        ]
    elif problem_type == "regression":
        candidate_algorithms = ["Linear Regression", "Random Forest Regressor", "Gradient Boosting Regressor"]
        recommended_pipeline = "Regression workflow with strong feature handling and validation."
        preprocessing_steps = [
            "Confirm the continuous target variable.",
            "Scale numeric features where appropriate.",
            "Handle missing values and encode categorical inputs.",
        ]
    elif problem_type == "clustering":
        candidate_algorithms = ["K-Means", "Hierarchical Clustering"]
        recommended_pipeline = "Unsupervised clustering workflow focused on grouping and similarity analysis."
        preprocessing_steps = [
            "Confirm the feature set used for similarity analysis.",
            "Scale numeric features before clustering.",
            "Review cluster quality and separability.",
        ]
    else:
        candidate_algorithms = []
        recommended_pipeline = "More information is required before a reliable ML pipeline can be recommended."
        preprocessing_steps = [
            "Clarify the target or objective.",
            "Confirm the dataset quality and feature definition.",
        ]

    if _has_missing_values(dataset_summary):
        preprocessing_steps.insert(0, "Handle missing values in the dataset before model fitting.")
    if _has_duplicate_rows(dataset_summary):
        preprocessing_steps.insert(1, "Remove duplicate rows before fitting the selected pipeline.")
    if _has_categorical_columns(dataset_summary):
        preprocessing_steps.append("Convert categorical columns to model-ready encodings.")
    if (dataset_summary.get("quality_score") or 0) < 80:
        preprocessing_steps.append("Review quality findings and address dataset issues before proceeding.")

    rationale = (
        f"The recommendation is based on a detected {problem_type} problem and the dataset profile. "
        "The selected pipeline stays conservative and prioritizes known-good preprocessing steps."
    )

    confidence = 0.72
    if problem_type == "unknown":
        confidence = 0.4
    elif _has_missing_values(dataset_summary) or _has_duplicate_rows(dataset_summary):
        confidence = 0.78
    elif (dataset_summary.get("quality_score") or 0) >= 80:
        confidence = 0.88

    warnings = list(warnings)
    if not state.get("target_candidate"):
        warnings.append("Target variable could not be determined automatically.")
    if problem_type == "unknown":
        warnings.append("Problem type is uncertain; more project context is required.")
    if not candidate_algorithms:
        warnings.append("No model candidates were inferred because the problem type is uncertain.")

    return {
        "recommended_pipeline": recommended_pipeline,
        "candidate_algorithms": candidate_algorithms,
        "preprocessing_steps": preprocessing_steps,
        "rationale": rationale,
        "confidence": confidence,
        "warnings": warnings,
    }
