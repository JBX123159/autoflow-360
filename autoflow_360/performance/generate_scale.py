from autoflow_360.performance.loader import load_tool


_tool = load_tool("autoflow_360_scale_tool", "generate_scale.py")

run = _tool.run
PROJECT_TARGET = _tool.PROJECT_TARGET
SAMPLE_TARGET = _tool.SAMPLE_TARGET
ORDER_TARGET = _tool.ORDER_TARGET
EVIDENCE_TARGET = _tool.EVIDENCE_TARGET
_record_counts = _tool._record_counts

__all__ = [
	"EVIDENCE_TARGET",
	"ORDER_TARGET",
	"PROJECT_TARGET",
	"SAMPLE_TARGET",
	"_record_counts",
	"run",
]
