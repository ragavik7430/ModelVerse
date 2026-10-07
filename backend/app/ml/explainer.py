import logging
import numpy as np
import shap

logger = logging.getLogger(__name__)

def explain_model(pipeline, algorithm: str, X_train, sample_size=100):
    try:
        # Supported tree-based algorithms
        tree_algorithms = ["Random Forest", "Random Forest Regressor", "Gradient Boosting", "Gradient Boosting Regressor"]
        linear_algorithms = ["Logistic Regression", "Linear Regression"]
        unsupported = ["K-Means"]

        if algorithm in unsupported:
            return {"error": "unsupported", "message": f"SHAP explanation is not supported for {algorithm}."}

        if len(X_train) > sample_size:
            X_sample = shap.sample(X_train, sample_size)
        else:
            X_sample = X_train

        preprocessor = pipeline.named_steps["preprocessing"]
        model = pipeline.named_steps["model"]

        X_transformed = preprocessor.transform(X_sample)
        if hasattr(X_transformed, "toarray"):
            X_transformed = X_transformed.toarray()

        try:
            if algorithm in tree_algorithms:
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(X_transformed)
            elif algorithm in linear_algorithms:
                explainer = shap.LinearExplainer(model, X_transformed)
                shap_values = explainer.shap_values(X_transformed)
            else:
                return {"error": "unsupported", "message": f"No valid SHAP explainer for {algorithm}."}
        except Exception as explainer_exc:
            logger.exception("Failed to initialize specific explainer.")
            return {"error": "unsupported", "message": f"Failed to compute SHAP for {algorithm}."}

        # Average over samples
        if isinstance(shap_values, list): # multi-class
            shap_values_mean = np.abs(shap_values).mean(axis=(0, 1))
        else:
            if len(shap_values.shape) > 2:
                shap_values_mean = np.abs(shap_values).mean(axis=(0, 2))
            else:
                shap_values_mean = np.abs(shap_values).mean(axis=0)

        if hasattr(preprocessor, "get_feature_names_out"):
            feature_names = preprocessor.get_feature_names_out()
        else:
            feature_names = [f"Feature {i}" for i in range(X_transformed.shape[1])]

        importances = {name: float(val) for name, val in zip(feature_names, shap_values_mean) if float(val) > 0}
        return dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

    except Exception as e:
        logger.exception("Explainability calculation failed.")
        return {"error": "failed", "message": f"Explainability failed: {str(e)}"}
