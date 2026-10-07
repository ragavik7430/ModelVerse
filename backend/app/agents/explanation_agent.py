import os
import json
import logging
from google import genai

logger = logging.getLogger(__name__)

def generate_natural_language_explanation(
    algorithm: str,
    problem_type: str,
    feature_importances: dict,
    rationale: str
) -> tuple[str, str]:
    """Returns (natural_language_explanation, limitations)"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return (
            "Explanation could not be generated because the LLM is not configured.",
            "Limitations unknown."
        )

    client = genai.Client(api_key=api_key)
    prompt = f"""
You are the Explanation Agent for ModelVerse.
The user has trained a {algorithm} model for a {problem_type} task.
Here is the original pipeline rationale from Phase 4: {rationale}

The SHAP feature importances (or native importances) calculated are:
{json.dumps(feature_importances, indent=2)}

Please provide:
1. A clear, plain-language explanation of which features most strongly influence the model's predictions.
Explain whether their contribution is positive or negative (if inferable, or speak generally about importance).
Clearly distinguish between model influence and true real-world causation (correlation vs causation).
2. The known limitations of this model type.

Format your output EXACTLY as a JSON object with two keys:
"natural_language_explanation": "..."
"limitations": "..."
Do not wrap it in markdown code blocks, just raw JSON.
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()

        result = json.loads(text)
        return result.get("natural_language_explanation", ""), result.get("limitations", "")
    except Exception as e:
        logger.error(f"Failed to generate explanation: {e}")
        return "Failed to generate plain-language explanation.", "Failed to retrieve limitations."
