import importlib.util
from pathlib import Path
from types import ModuleType


def load_tool(module_name: str, filename: str) -> ModuleType:
	tool_path = Path(__file__).resolve().parents[2] / "tests" / "performance" / filename
	if not tool_path.exists():
		raise ImportError(f"Performance tool is missing: {tool_path}")
	spec = importlib.util.spec_from_file_location(module_name, tool_path)
	if not spec or not spec.loader:
		raise ImportError(f"Performance tool cannot be loaded: {tool_path}")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module
