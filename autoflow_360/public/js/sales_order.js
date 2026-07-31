frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (!frm.doc.custom_source_quotation) {
			return;
		}
		frm.add_custom_button(__("Source Quotation"), () => {
			frappe.set_route("Form", "Quotation", frm.doc.custom_source_quotation);
		}, __("AutoFlow 360"));
	},
});
