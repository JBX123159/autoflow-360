from typing import Protocol


class ProviderError(RuntimeError):
	def __init__(self, code: str):
		super().__init__(code)
		self.code = code


class AIProvider(Protocol):
	name: str

	def generate(
		self,
		*,
		model: str,
		messages: list[dict],
		timeout_seconds: int,
	) -> dict: ...
