def after_install() -> None:
	from autoflow_360.setup.custom_fields import ensure_custom_fields
	from autoflow_360.setup.roles import ensure_roles
	from autoflow_360.setup.workflows import ensure_workflows

	ensure_roles()
	ensure_custom_fields()
	ensure_workflows()


def after_migrate() -> None:
	after_install()
