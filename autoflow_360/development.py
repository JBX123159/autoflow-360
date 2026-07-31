import os

import frappe
from frappe.utils.password import update_password


def sync_local_admin_password() -> str:
    """Synchronize the local development Administrator password from the process environment."""
    site_name = frappe.local.site or ""
    if not site_name.endswith(".localhost"):
        frappe.throw("管理员密码同步只允许用于 .localhost 本地开发站点。")
    if not frappe.conf.developer_mode:
        frappe.throw("管理员密码同步只允许在 developer_mode 中执行。")

    password = os.environ.get("AUTOFLOW_ADMIN_PASSWORD", "")
    if len(password) < 12:
        frappe.throw("AUTOFLOW_ADMIN_PASSWORD 至少需要 12 个字符。")

    update_password(
        user="Administrator",
        pwd=password,
        logout_all_sessions=True,
    )
    frappe.db.commit()
    return "updated"
