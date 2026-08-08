from autoflow_360.ai.providers.base import ProviderError


class DisabledProvider:
	name = "disabled"

	def generate(
		self,
		*,
		model: str,
		messages: list[dict],
		timeout_seconds: int,
	) -> dict:
		raise ProviderError("provider_disabled")
