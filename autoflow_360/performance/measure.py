from autoflow_360.performance.loader import load_tool


_tool = load_tool("autoflow_360_measure_tool", "measure.py")
run = _tool.run

__all__ = ["run"]
