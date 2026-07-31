const exceptionTransitions = {
	"已发现": ["已分级", "已取消"],
	"已分级": ["已分派", "已取消"],
	"已分派": ["根因分析中", "已取消"],
	"根因分析中": ["整改中", "已取消"],
	"整改中": ["待验证", "已取消"],
	"待验证": ["已关闭", "整改中"],
};

async function postExceptionTransition(frm, targetStatus, values = {}) {
	await frappe.call({
		method: "autoflow_360.api.exception.change_exception_status",
		type: "POST",
		args: {
			exception_name: frm.doc.name,
			target_status: targetStatus,
			evidence: values.verification_evidence || null,
			reason: values.cancellation_reason || null,
		},
		freeze: true,
		freeze_message: __("Updating business exception..."),
	});
	await frm.reload_doc();
}

function requestExceptionTransition(frm, targetStatus) {
	if (targetStatus === "已关闭") {
		const dialog = new frappe.ui.Dialog({
			title: __("Independent Verification"),
			fields: [{
				fieldname: "verification_evidence",
				fieldtype: "Attach",
				label: __("Verification Evidence"),
				reqd: 1,
			}],
			primary_action_label: __("Close Exception"),
			primary_action: async (values) => {
				dialog.disable_primary_action();
				try {
					await postExceptionTransition(frm, targetStatus, values);
					dialog.hide();
				} finally {
					dialog.enable_primary_action();
				}
			},
		});
		dialog.show();
		return;
	}
	if (targetStatus === "已取消") {
		frappe.prompt(
			[{ fieldname: "cancellation_reason", fieldtype: "Small Text", label: __("Cancellation Reason"), reqd: 1 }],
			(values) => postExceptionTransition(frm, targetStatus, values),
			__("Cancel Business Exception"),
			__("Cancel Exception"),
		);
		return;
	}
	frappe.confirm(
		__("Move this exception to {0}?", [__(targetStatus)]),
		() => postExceptionTransition(frm, targetStatus),
	);
}

frappe.ui.form.on("Business Exception", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		(exceptionTransitions[frm.doc.status] || []).forEach((targetStatus) => {
			frm.add_custom_button(__(targetStatus), () => {
				requestExceptionTransition(frm, targetStatus);
			}, __("Workflow"));
		});
	},
});
