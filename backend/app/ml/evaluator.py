from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score, silhouette_score


COMPARISON_POLICIES = {
    "regression": "Lowest validation RMSE; ties resolve by algorithm name.",
    "classification": "Highest validation macro F1, then accuracy; ties resolve by algorithm name.",
    "clustering": "Highest validation silhouette score; ties resolve by algorithm name.",
}


def _number_or_none(value: Any) -> float | None:
    numeric = float(value)
    return numeric if np.isfinite(numeric) else None


def _regression_metrics(actual, predicted) -> dict[str, float | None]:
    mse = float(mean_squared_error(actual, predicted))
    return {
        "mae": _number_or_none(mean_absolute_error(actual, predicted)),
        "mse": _number_or_none(mse),
        "rmse": _number_or_none(np.sqrt(mse)),
        "r2": _number_or_none(r2_score(actual, predicted)) if len(actual) > 1 else None,
    }


def _classification_metrics(actual, predicted, labels: list[Any]) -> dict[str, Any]:
    return {
        "accuracy": _number_or_none(accuracy_score(actual, predicted)),
        "precision_macro": _number_or_none(precision_score(actual, predicted, average="macro", zero_division=0)),
        "recall_macro": _number_or_none(recall_score(actual, predicted, average="macro", zero_division=0)),
        "f1_macro": _number_or_none(f1_score(actual, predicted, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(actual, predicted, labels=labels).tolist(),
        "class_labels": [value.item() if hasattr(value, "item") else value for value in labels],
    }


def _silhouette(features, labels) -> float | None:
    unique_labels = np.unique(labels)
    if len(unique_labels) < 2 or len(unique_labels) >= len(labels):
        return None
    return _number_or_none(silhouette_score(features, labels))


def evaluate_supervised(problem_type: str, y_train, train_predictions, y_validation, validation_predictions, y_test, test_predictions) -> dict[str, Any]:
    if problem_type == "regression":
        metric_function = _regression_metrics
        return {
            "train": metric_function(y_train, train_predictions),
            "validation": metric_function(y_validation, validation_predictions),
            "test": metric_function(y_test, test_predictions),
        }

    labels = sorted(set(y_train), key=lambda value: str(value))
    return {
        "train": _classification_metrics(y_train, train_predictions, labels),
        "validation": _classification_metrics(y_validation, validation_predictions, labels),
        "test": _classification_metrics(y_test, test_predictions, labels),
    }


def evaluate_clustering(train_features, train_labels, validation_features, validation_labels, test_features, test_labels) -> dict[str, Any]:
    return {
        "train": {"silhouette": _silhouette(train_features, train_labels)},
        "validation": {"silhouette": _silhouette(validation_features, validation_labels)},
        "test": {"silhouette": _silhouette(test_features, test_labels)},
        "metric_note": "Silhouette measures cluster separation on each held-out feature split; it does not use target labels.",
    }


def select_best_model(problem_type: str, completed_models: list[Any]) -> Any | None:
    policy = {
        "regression": lambda model: (
            model.metrics.get("validation", {}).get("rmse") is None,
            model.metrics.get("validation", {}).get("rmse") if model.metrics.get("validation", {}).get("rmse") is not None else float("inf"),
            model.algorithm,
        ),
        "classification": lambda model: (
            model.metrics.get("validation", {}).get("f1_macro") is None,
            -(model.metrics.get("validation", {}).get("f1_macro") or 0.0),
            -(model.metrics.get("validation", {}).get("accuracy") or 0.0),
            model.algorithm,
        ),
        "clustering": lambda model: (
            model.metrics.get("validation", {}).get("silhouette") is None,
            -(model.metrics.get("validation", {}).get("silhouette") or 0.0),
            model.algorithm,
        ),
    }.get(problem_type)
    if policy is None:
        raise ValueError("No comparison policy exists for this problem type.")
    eligible = [
        model for model in completed_models
        if model.status == "completed"
        and model.metrics.get("validation", {}).get(
            "rmse" if problem_type == "regression" else "f1_macro" if problem_type == "classification" else "silhouette"
        ) is not None
    ]
    return min(eligible, key=policy) if eligible else None
