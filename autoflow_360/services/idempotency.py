import hashlib
import json


def make_idempotency_key(operation: str, *parts: str) -> str:
	"""Build a stable key without ambiguous string concatenation."""
	normalized_operation = str(operation).strip()
	if not normalized_operation:
		raise ValueError("operation is required")

	payload = [normalized_operation, *(str(part).strip() for part in parts)]
	serialized = json.dumps(
		payload,
		ensure_ascii=False,
		separators=(",", ":"),
	)
	return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
