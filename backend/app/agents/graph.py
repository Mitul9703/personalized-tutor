# Wires the agent nodes into a LangGraph graph. The graph holds the control
# flow and decides the order; the agents hand off through shared state and
# never call each other. The router classifies the turn; answer and clarify
# turns skip the build pipeline and go to the QA agent, which replies in
# chat with citations.

from langgraph.graph import StateGraph, END

from app.agents.state import TurnState
from app.agents import nodes


def build_graph(session):
    graph = StateGraph(TurnState)

    graph.add_node("router", lambda s: nodes.router(s, session))
    graph.add_node("qa", lambda s: nodes.qa(s, session))
    graph.add_node("revert", lambda s: nodes.revert(s, session))
    graph.add_node("planner", lambda s: nodes.planner(s, session))
    graph.add_node("builder", lambda s: nodes.builder(s, session))
    graph.add_node("critic", lambda s: nodes.critic(s, session))
    graph.add_node("finalize", lambda s: nodes.finalize(s, session))

    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        nodes.route_after_router,
        {"planner": "planner", "qa": "qa", "revert": "revert"},
    )
    graph.add_edge("planner", "builder")
    graph.add_edge("builder", "critic")
    graph.add_conditional_edges(
        "critic",
        nodes.route_after_critic,
        {"finalize": "finalize", "builder": "builder"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("qa", END)
    graph.add_edge("revert", END)

    return graph.compile()
