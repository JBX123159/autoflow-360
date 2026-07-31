frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		if (frm.doc.custom_source_supplier_quotation) {
			frm.add_custom_button(__("Source Supplier Quotation"), () => {
				frappe.set_route(
					"Form",
					"Supplier Quotation",
					frm.doc.custom_source_supplier_quotation,
				);
			}, __("AutoFlow 360"));
		}
		if (
			frm.doc.docstatus !== 1 ||
			["Closed", "Completed", "Cancelled"].includes(frm.doc.status)
		) {
			return;
		}

		frm.add_custom_button(__("Update Supplier ETA"), () => {
			frappe.prompt(
				[
					{
						fieldname: "eta",
						fieldtype: "Date",
						label: __("New Supplier ETA"),
						default: frm.doc.custom_supplier_eta || frm.doc.schedule_date,
						reqd: 1,
					},
					{
						fieldname: "reason",
						fieldtype: "Small Text",
						label: __("Change Reason"),
						reqd: 1,
					},
				],
				async (values) => {
					await frappe.call({
						method: "autoflow_360.api.procurement.set_supplier_eta",
						type: "POST",
						args: {
							purchase_order_name: frm.doc.name,
							eta: values.eta,
							reason: values.reason,
						},
						freeze: true,
						freeze_message: __("Recording supplier ETA..."),
					});
					await frm.reload_doc();
				},
				__("Update ETA"),
				__("Supplier ETA"),
			);
		}, __("AutoFlow 360"));
	},
});
