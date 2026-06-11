"""Static analyzer - delegates to the deterministic WordPress rules analyzer."""
from analysis.agents_rules_analyzer import AgentsRulesAnalyzer as StaticAnalyzer

__all__ = ["StaticAnalyzer"]
