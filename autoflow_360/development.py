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


def complete_local_demo_setup() -> str:
    """Refresh setup state after synthetic demo data is created on a local site."""
    site_name = frappe.local.site or ""
    if not site_name.endswith(".localhost"):
        frappe.throw("演示站点初始化收尾只允许用于 .localhost 本地开发站点。")
    if not frappe.conf.developer_mode:
        frappe.throw("演示站点初始化收尾只允许在 developer_mode 中执行。")

    company = frappe.db.get_value("Company", {}, "name")
    system_user = frappe.db.get_value(
        "User",
        {
            "user_type": "System User",
            "name": ["not in", ["Administrator", "Guest"]],
        },
        "name",
    )
    if not company or not system_user:
        frappe.throw("演示公司和非管理员系统用户创建完成后才能结束首次设置。")

    frappe.get_single("Installed Applications").update_versions()
    frappe.clear_cache()
    if not frappe.is_setup_complete():
        frappe.throw("Frappe 与 ERPNext 的首次设置状态仍未完成。")

    frappe.db.commit()
    return "completed"
