# Wires the agent nodes into a LangGraph graph. The graph holds the control
# flow so one turn always runs the same way: orchestrator, planner, builder,
# critic, then finalize. If the critic fails it sends the builder back, up
# to a cap. We pass the database session into each node with a small
# wrapper.

from langgraph.graph import StateGraph, END

from app.agents.state import TurnState
from app.agents import nodes


def build_graph(session):
    graph = StateGraph(TurnState)

    graph.add_node("orchestrator", lambda s: nodes.orchestrator(s, session))
    graph.add_node("planner", lambda s: nodes.planner(s, session))
    graph.add_node("builder", lambda s: nodes.builder(s, session))
    graph.add_node("critic", lambda s: nodes.critic(s, session))
    graph.add_node("finalize", lambda s: nodes.finalize(s, session))

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "planner")
    graph.add_edge("planner", "builder")
    graph.add_edge("builder", "critic")
    graph.add_conditional_edges(
        "critic",
        nodes.route_after_critic,
        {"finalize": "finalize", "builder": "builder"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()
