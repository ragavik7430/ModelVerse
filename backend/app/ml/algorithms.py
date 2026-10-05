from collections.abc import Callable
from typing import Any

from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression


EstimatorFactory = Callable[[int, dict[str, Any]], Any]


def _logistic_regression(random_state: int, parameters: dict[str, Any]):
    return LogisticRegression(max_iter=1000, random_state=random_state, **parameters)


def _random_forest_classifier(random_state: int, parameters: dict[str, Any]):
    return RandomForestClassifier(random_state=random_state, n_jobs=1, **parameters)


def _gradient_boosting_classifier(random_state: int, parameters: dict[str, Any]):
    return GradientBoostingClassifier(random_state=random_state, **parameters)


def _linear_regression(random_state: int, parameters: dict[str, Any]):
    del random_state
    return LinearRegression(**parameters)


def _random_forest_regressor(random_state: int, parameters: dict[str, Any]):
    return RandomForestRegressor(random_state=random_state, n_jobs=1, **parameters)


def _gradient_boosting_regressor(random_state: int, parameters: dict[str, Any]):
    return GradientBoostingRegressor(random_state=random_state, **parameters)


def _kmeans(random_state: int, parameters: dict[str, Any]):
    options = {"random_state": random_state, "n_init": 10, "n_clusters": 2}
    options.update(parameters)
    return KMeans(**options)


ALGORITHM_FACTORIES: dict[str, dict[str, EstimatorFactory]] = {
    "classification": {
        "Logistic Regression": _logistic_regression,
        "Random Forest": _random_forest_classifier,
        "Gradient Boosting": _gradient_boosting_classifier,
    },
    "regression": {
        "Linear Regression": _linear_regression,
        "Random Forest Regressor": _random_forest_regressor,
        "Gradient Boosting Regressor": _gradient_boosting_regressor,
    },
    "clustering": {
        "K-Means": _kmeans,
    },
}


def supported_recommendations(problem_type: str, recommended: list[str]) -> list[str]:
    supported = ALGORITHM_FACTORIES.get(problem_type, {})
    return [name for name in recommended if name in supported]


def create_estimator(problem_type: str, algorithm: str, random_state: int, parameters: dict[str, Any] | None = None):
    factory = ALGORITHM_FACTORIES.get(problem_type, {}).get(algorithm)
    if factory is None:
        raise ValueError("The selected algorithm is not supported for this problem type.")
    return factory(random_state, parameters or {})
