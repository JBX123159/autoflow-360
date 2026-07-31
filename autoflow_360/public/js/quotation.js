frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.custom_customer_project) {
			return;
		}

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Request Price Approval"), async () => {
				const response = await frappe.call({
					method: "autoflow_360.api.sales.request_quotation_approval",
					type: "POST",
					args: { quotation_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Creating approval request..."),
				});
				frappe.set_route("Form", "AutoFlow Approval Request", response.message);
			}, __("AutoFlow 360"));
		}

		if (frm.doc.docstatus === 1 && frm.doc.custom_customer_confirmed) {
			frm.add_custom_button(__("Create Sales Order"), async () => {
				const response = await frappe.call({
					method: "autoflow_360.api.sales.create_sales_order",
					type: "POST",
					args: { quotation_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Creating sales order..."),
				});
				frappe.set_route("Form", "Sales Order", response.message);
			}, __("AutoFlow 360"));
		}
	},
});
