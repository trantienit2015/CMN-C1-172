"""CMN-C1-172 — Graph composition + routing unit tests."""
from __future__ import annotations

from framework.graph.agent_base_graph import AgentBaseGraph
from src.graph.graph import EnterprisePrivateDocSearchAgent, Graph
from src.nodes.leann_search_node import LeannSearchNode
from src.nodes.query_normalize_node import QueryNormalizeNode
from src.nodes.response_format_node import ResponseFormatNode
from src.schemas.state import CMNPrivateDocSearchState


class TestGraphComposition:
    def test_graph_inherits_agentbasegraph_l1_direct(self):
        assert issubclass(EnterprisePrivateDocSearchAgent, AgentBaseGraph)

    def test_graph_alias(self):
        assert Graph is EnterprisePrivateDocSearchAgent

    def test_name_matches_agent_yaml(self):
        assert EnterprisePrivateDocSearchAgent().name == "EnterprisePrivateDocSearchAgent"

    def test_state_schema_is_domain_state(self):
        assert EnterprisePrivateDocSearchAgent().state_schema is CMNPrivateDocSearchState

    def test_register_nodes_fills_three_domain_slots(self):
        graph = EnterprisePrivateDocSearchAgent()
        graph.register_nodes()
        assert isinstance(graph._nodes["pre_process"], QueryNormalizeNode)
        assert isinstance(graph._nodes["main"], LeannSearchNode)
        assert isinstance(graph._nodes["post_process"], ResponseFormatNode)
        # framework backbone nodes injected by super().register_nodes()
        assert graph._nodes["initialize"] is not None
        assert graph._nodes["finalize"] is not None
