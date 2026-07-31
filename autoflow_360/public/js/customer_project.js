function escapeClosureText(value) {
	return frappe.utils.escape_html(String(value || ""));
}

function showClosureStatus(status) {
	if (!status.gaps.length) {
		frappe.msgprint({
			title: __("Closure Readiness"),
			indicator: "green",
			message: __("All delivery, billing, collection, receipt, and risk checks passed."),
		});
		return;
	}
	const items = status.gaps.map((gap) => {
		const reference = gap.reference_name
			? ` · ${escapeClosureText(gap.reference_doctype)} ${escapeClosureText(gap.reference_name)}`
			: "";
		return `<li><strong>${escapeClosureText(gap.code)}</strong> · ${escapeClosureText(gap.message)}${reference}</li>`;
	});
	frappe.msgprint({
		title: __("Closure Gaps"),
		indicator: "orange",
		message: `<ul>${items.join("")}</ul>`,
	});
}

async function getClosureStatus(frm) {
	const response = await frappe.call({
		method: "autoflow_360.api.project.get_project_closure_status",
		type: "GET",
		args: { project_name: frm.doc.name },
	});
	return response.message;
}

async function requestClosureApproval(frm) {
	const response = await frappe.call({
		method: "autoflow_360.api.project.request_project_closure",
		type: "POST",
		args: { project_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Creating closure approval request..."),
	});
	frappe.set_route("Form", "AutoFlow Approval Request", response.message);
}

function finalizeClosure(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Close Customer Project"),
		fields: [
			{
				fieldname: "closure_summary",
				fieldtype: "Long Text",
				label: __("Closure Summary"),
				reqd: 1,
				description: __("Record the delivery result, collection result, lessons learned, and follow-up actions."),
			},
		],
		primary_action_label: __("Close Project"),
		primary_action: async (values) => {
			dialog.disable_primary_action();
			try {
				await frappe.call({
					method: "autoflow_360.api.project.finalize_project_closure",
					type: "POST",
					args: {
						project_name: frm.doc.name,
						closure_summary: values.closure_summary,
					},
					freeze: true,
					freeze_message: __("Closing customer project..."),
				});
				dialog.hide();
				await frm.reload_doc();
			} finally {
				dialog.enable_primary_action();
			}
		},
	});
	dialog.show();
}

frappe.ui.form.on("Customer Project", {
	async refresh(frm) {
		if (frm.is_new() || ["暂停", "失败", "取消", "已结项"].includes(frm.doc.stage)) {
			return;
		}
		frm.add_custom_button(__("Check Closure Readiness"), async () => {
			showClosureStatus(await getClosureStatus(frm));
		}, __("Closure"));

		const status = await getClosureStatus(frm);
		if (!status.gaps.length && !status.approved) {
			frm.add_custom_button(__("Request Closure Approval"), () => {
				requestClosureApproval(frm);
			}, __("Closure"));
		}
		if (!status.gaps.length && status.approved) {
			frm.add_custom_button(__("Close Project"), () => {
				finalizeClosure(frm);
			}, __("Closure"));
		}
	},
});
