def after_install() -> None:
	from autoflow_360.setup.custom_fields import ensure_custom_fields
	from autoflow_360.setup.roles import ensure_roles

	ensure_roles()
	ensure_custom_fields()


def after_migrate() -> None:
	after_install()
