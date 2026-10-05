from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def build_preprocessor(features: pd.DataFrame) -> tuple[ColumnTransformer, dict[str, Any]]:
    numeric_columns = list(features.select_dtypes(include=["number"]).columns)
    categorical_columns = [column for column in features.columns if column not in numeric_columns]

    transformers = []
    if numeric_columns:
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scaler", StandardScaler()),
            ]
        )
        transformers.append(("numeric", numeric_pipeline, numeric_columns))
    if categorical_columns:
        categorical_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value="__missing__")),
                ("encoder", OneHotEncoder(handle_unknown="ignore")),
            ]
        )
        transformers.append(("categorical", categorical_pipeline, categorical_columns))

    if not transformers:
        raise ValueError("No usable feature columns remain after selecting the target.")

    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
    configuration = {
        "fit_scope": "training split only",
        "numeric": {
            "columns": numeric_columns,
            "missing_values": "median imputation",
            "scaling": "standard scaling",
        },
        "categorical": {
            "columns": categorical_columns,
            "missing_values": "constant '__missing__' imputation",
            "encoding": "one-hot; unseen values ignored",
        },
    }
    return preprocessor, configuration


def build_training_pipeline(features: pd.DataFrame, estimator):
    preprocessor, configuration = build_preprocessor(features)
    pipeline = Pipeline(steps=[("preprocessing", preprocessor), ("model", estimator)])
    return pipeline, configuration
