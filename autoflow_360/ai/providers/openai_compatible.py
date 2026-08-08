import json

import requests

from autoflow_360.ai.providers.base import ProviderError


MAX_RESPONSE_CHARACTERS = 131_072


def _decode_content(content) -> dict:
	if isinstance(content, dict):
		return content
	if not isinstance(content, str) or len(content) > MAX_RESPONSE_CHARACTERS:
		raise ProviderError("invalid_provider_response")
	content = content.strip()
	if content.startswith("```json") and content.endswith("```"):
		content = content[7:-3].strip()
	elif content.startswith("```") and content.endswith("```"):
		content = content[3:-3].strip()
	try:
		payload = json.loads(content)
	except (TypeError, ValueError) as error:
		raise ProviderError("invalid_provider_response") from error
	if not isinstance(payload, dict):
		raise ProviderError("invalid_provider_response")
	return payload


class OpenAICompatibleProvider:
	name = "openai-compatible"

	def __init__(self, base_url: str, api_key: str = ""):
		self.base_url = base_url.rstrip("/")
		self.api_key = api_key

	def generate(
		self,
		*,
		model: str,
		messages: list[dict],
		timeout_seconds: int,
	) -> dict:
		headers = {"Content-Type": "application/json"}
		if self.api_key:
			headers["Authorization"] = f"Bearer {self.api_key}"
		try:
			response = requests.post(
				f"{self.base_url}/chat/completions",
				headers=headers,
				json={
					"model": model,
					"messages": messages,
					"temperature": 0,
					"response_format": {"type": "json_object"},
				},
				timeout=timeout_seconds,
			)
		except requests.Timeout as error:
			raise ProviderError("provider_timeout") from error
		except requests.ConnectionError as error:
			raise ProviderError("provider_connection") from error
		except requests.RequestException as error:
			raise ProviderError("provider_request_failed") from error

		if response.status_code == 429:
			raise ProviderError("provider_rate_limited")
		if response.status_code in {401, 403}:
			raise ProviderError("provider_authentication")
		if response.status_code >= 500:
			raise ProviderError("provider_unavailable")
		if not response.ok:
			raise ProviderError("provider_http_error")
		try:
			payload = response.json()
			content = payload["choices"][0]["message"]["content"]
		except (KeyError, IndexError, TypeError, ValueError) as error:
			raise ProviderError("invalid_provider_response") from error
		return _decode_content(content)
