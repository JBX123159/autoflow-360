frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.custom_source_quotation) {
			frm.add_custom_button(__("Source Quotation"), () => {
				frappe.set_route("Form", "Quotation", frm.doc.custom_source_quotation);
			}, __("AutoFlow 360"));
		}

		const blocked_statuses = ["On Hold", "Closed"];
		if (
			frm.doc.docstatus !== 1 ||
			!frm.doc.custom_customer_project ||
			blocked_statuses.includes(frm.doc.status)
		) {
			return;
		}

		frm.add_custom_button(__("Plan Materials"), () => {
			frappe.call({
				method: "autoflow_360.api.material.plan_sales_order",
				args: { sales_order_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Calculating material demand..."),
			}).then(({ message }) => {
				if (message?.material_request) {
					frappe.set_route("Form", "Material Request", message.material_request);
					return;
				}
				if (message?.material_plan) {
					frappe.show_alert({ message: __("No material shortage found."), indicator: "green" });
					frappe.set_route("Form", "Project Material Plan", message.material_plan);
					return;
				}
				frappe.show_alert({ message: __("No stock items require planning."), indicator: "blue" });
			});
		}, __("AutoFlow 360"));
	},
});
