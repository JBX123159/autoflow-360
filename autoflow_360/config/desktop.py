from frappe import _


def get_data() -> list[dict]:
	return [
		{
			"module_name": "AutoFlow 360",
			"type": "module",
			"label": _("AutoFlow 360"),
			"color": "#1D4ED8",
			"icon": "octicon octicon-workflow",
		}
	]
