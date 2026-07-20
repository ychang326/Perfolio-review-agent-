"""Agent implementations."""

from .orchestrator import OrchestratorAgent
from .product_agent import KnowledgeAgentNode, ProductAgentNode
from .billing_agent import HoldingsAgentNode, BillingAgentNode
from .promotion_agent import AttributionAgentNode, PromotionAgentNode
from .recommendation_agent import PerformanceAgent, RecommendationAgent
from .finops_agent import RiskAgentNode, FinOpsAgentNode

__all__ = [
    "OrchestratorAgent",
    "KnowledgeAgentNode",
    "HoldingsAgentNode",
    "AttributionAgentNode",
    "PerformanceAgent",
    "RiskAgentNode",
    # backward-compatible aliases
    "ProductAgentNode",
    "BillingAgentNode",
    "PromotionAgentNode",
    "RecommendationAgent",
    "FinOpsAgentNode",
]
