frappe.ui.form.on("Material Request", {
	refresh(frm) {
		if (frm.doc.custom_source_sales_order) {
			frm.add_custom_button(__("Source Sales Order"), () => {
				frappe.set_route("Form", "Sales Order", frm.doc.custom_source_sales_order);
			}, __("AutoFlow 360"));
		}
		if (
			frm.doc.docstatus !== 1 ||
			frm.doc.material_request_type !== "Purchase" ||
			!frm.doc.custom_customer_project
		) {
			return;
		}

		frm.add_custom_button(__("Create Project RFQ"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Select Suppliers"),
				fields: [
					{
						fieldname: "suppliers",
						fieldtype: "MultiSelectList",
						label: __("Suppliers"),
						options: "Supplier",
						reqd: 1,
						get_data: (text) => frappe.db.get_link_options("Supplier", text),
					},
				],
				primary_action_label: __("Create RFQ"),
				primary_action: async (values) => {
					const suppliers = (values.suppliers || [])
						.map((value) => typeof value === "string" ? value : value.value)
						.filter(Boolean);
					if (!suppliers.length) {
						frappe.msgprint(__("Select at least one supplier."));
						return;
					}
					dialog.hide();
					const response = await frappe.call({
						method: "autoflow_360.api.procurement.create_rfq",
						type: "POST",
						args: {
							material_request_name: frm.doc.name,
							suppliers,
						},
						freeze: true,
						freeze_message: __("Creating supplier RFQ..."),
					});
					frappe.set_route("Form", "Request for Quotation", response.message);
				},
			});
			dialog.show();
		}, __("AutoFlow 360"));
	},
});
