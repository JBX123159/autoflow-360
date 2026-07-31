frappe.ui.form.on("Supplier Quotation", {
	refresh(frm) {
		if (frm.doc.custom_source_rfq) {
			frm.add_custom_button(__("Source RFQ"), () => {
				frappe.set_route("Form", "Request for Quotation", frm.doc.custom_source_rfq);
			}, __("AutoFlow 360"));
		}
		if (frm.doc.docstatus !== 1 || !frm.doc.custom_customer_project) {
			return;
		}

		frm.add_custom_button(__("Create Purchase Order"), async () => {
			const response = await frappe.call({
				method: "autoflow_360.api.procurement.create_purchase_order",
				type: "POST",
				args: { supplier_quotation_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Creating purchase order..."),
			});
			frappe.set_route("Form", "Purchase Order", response.message);
		}, __("AutoFlow 360"));
	},
});
