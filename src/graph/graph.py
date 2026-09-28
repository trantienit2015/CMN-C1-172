"""CMN-C1-172 — Graph composition (L1-direct AgentBaseGraph).

The graph class IS the agent. It inherits L1 ``AgentBaseGraph`` directly (no L2
base agent, no separate agent class, no nested graph). ``register_nodes()`` calls
``super().register_nodes()`` first to inject the framework ``initialize`` /
``finalize`` backbone nodes, then fills the three domain slots:

    initialize → pre_process → main → post_process → finalize

  - pre_process : QueryNormalizeNode   (normalize + S-2 input gate)
  - main        : LeannSearchNode      (on-device LEANN search + access control + PII redaction)
  - post_process: ResponseFormatNode   (render markdown + APPI 2026 advisory)

No business logic lives here; nodes (and their services) own that. The public
entry is ``Graph().compile()`` then ``agent.invoke(user_input, ctx=ctx)`` — never
``.run()``. The framework owns routing, the S-1 trust gate, timing, error
capture, and node_history.
"""

from __future__ import annotations

from framework.graph.agent_base_graph import AgentBaseGraph

from src.nodes.leann_search_node import LeannSearchNode
from src.nodes.query_normalize_node import QueryNormalizeNode
from src.nodes.response_format_node import ResponseFormatNode
from src.schemas.state import CMNPrivateDocSearchState

_DEFAULT_TOP_K = 10


class EnterprisePrivateDocSearchAgent(AgentBaseGraph):
    """Enterprise Private Document Corpus Search Agent (LEANN On-Device RAG).

    Cat 1 — single technical capability (on-device private document search).
    On-device only; no data leaves the local process (APPI 2026 data minimization
    by architecture; 電子帳簿保存法 2024 corpus compatible).
    """

    @property
    def name(self) -> str:
        return "EnterprisePrivateDocSearchAgent"

    @property
    def state_schema(self) -> type:
        return CMNPrivateDocSearchState

    def register_nodes(self) -> None:
        super().register_nodes()  # injects default initialize + finalize backbone nodes

        top_k = self.config.get("top_k", _DEFAULT_TOP_K) if hasattr(self, "config") else _DEFAULT_TOP_K
        self._nodes["pre_process"] = QueryNormalizeNode()
        self._nodes["main"] = LeannSearchNode(top_k=top_k)
        self._nodes["post_process"] = ResponseFormatNode()


# Stable alias for the standalone entry point import (src/api/server.py).
# import a stable name.
Graph = EnterprisePrivateDocSearchAgent
