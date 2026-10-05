from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import END, StateGraph

from app.agents.nodes.dataset_analysis import analyze_dataset_node
from app.agents.nodes.pipeline_recommendation import recommend_pipeline_node
from app.agents.nodes.problem_analysis import analyze_problem_node
from app.agents.nodes.recommendation_explanation import explain_recommendation_node
from app.agents.state import GraphState


def build_graph():
    workflow = StateGraph(GraphState)
    workflow.add_node("problem_analysis", analyze_problem_node)
    workflow.add_node("dataset_analysis", analyze_dataset_node)
    workflow.add_node("pipeline_recommendation", recommend_pipeline_node)
    workflow.add_node("recommendation_explanation", explain_recommendation_node)

    workflow.set_entry_point("problem_analysis")
    workflow.add_edge("problem_analysis", "dataset_analysis")
    workflow.add_edge("dataset_analysis", "pipeline_recommendation")
    workflow.add_edge("pipeline_recommendation", "recommendation_explanation")
    workflow.add_edge("recommendation_explanation", END)
    return workflow.compile()


def execute_agent_graph(state: Dict[str, Any]) -> Dict[str, Any]:
    graph = build_graph()
    result = graph.invoke(state)
    if not isinstance(result, dict):
        raise TypeError("Recommendation graph did not return a dictionary state.")
    return result
