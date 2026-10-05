from __future__ import annotations

from typing import Any, Dict, Iterable


def _total_missing_values(summary: Dict[str, Any]) -> int:
    missing_values = summary.get("missing_values") or {}
    return sum(int(value) for value in missing_values.values() if isinstance(value, (int, float)))


def analyze_dataset_node(state: Dict[str, Any]) -> Dict[str, Any]:
    summary = state.get("dataset_summary") or {}
    if not summary:
        return {
            "dataset_characteristics": {},
            "feature_candidates": [],
            "warnings": ["Dataset summary was not available for analysis."],
            "errors": ["Dataset summary is missing."],
        }

    numeric_columns = summary.get("numeric_columns") or []
    categorical_columns = summary.get("categorical_columns") or []
    columns = summary.get("columns") or []
    missing_values = summary.get("missing_values") or {}
    quality_status = summary.get("quality_status") or "unknown"
    quality_score = summary.get("quality_score") or 0
    duplicate_rows = int(summary.get("duplicate_rows") or 0)

    feature_candidates = list(columns)
    warnings: list[str] = []
    if duplicate_rows > 0:
        warnings.append(f"Duplicate rows detected: {duplicate_rows} duplicates.")
    if _total_missing_values(summary) > 0:
        warnings.append("Missing values are present and may require preprocessing.")
    if quality_score < 80:
        warnings.append(f"Dataset quality score is {quality_score}, so more review is recommended.")
    if quality_status in {"failed", "warning"}:
        warnings.append(f"Dataset quality status is {quality_status}.")

    dataset_characteristics = {
        "row_count": int(summary.get("row_count") or 0),
        "column_count": int(summary.get("column_count") or 0),
        "numeric_columns": list(numeric_columns),
        "categorical_columns": list(categorical_columns),
        "missing_values": {str(key): int(value) for key, value in dict(missing_values).items()},
        "duplicate_rows": duplicate_rows,
        "quality_score": int(quality_score),
        "quality_status": quality_status,
        "findings": summary.get("findings") or [],
    }

    return {
        "dataset_characteristics": dataset_characteristics,
        "feature_candidates": feature_candidates,
        "warnings": warnings,
    }
