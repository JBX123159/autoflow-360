"""Canonical Frappe test-record boundary for AutoFlow Approval Request.

The integration scenarios live in ``test_sales_conversion.py``. Frappe v16
loads this canonical module while resolving DocType dependencies, so the
optional ERPNext payment stack must be excluded here as well.
"""


IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"User",
]
