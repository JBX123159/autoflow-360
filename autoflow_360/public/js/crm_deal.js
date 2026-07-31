frappe.ui.form.on("CRM Deal", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Create or Open Customer Project"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Convert Deal to Customer Project"),
				fields: [
					{
						fieldname: "company",
						fieldtype: "Link",
						label: __("Company"),
						options: "Company",
						reqd: 1,
					},
					{
						fieldname: "customer",
						fieldtype: "Link",
						label: __("Customer"),
						options: "Customer",
						reqd: 1,
					},
					{
						fieldname: "product_family",
						fieldtype: "Data",
						label: __("Product Family"),
						reqd: 1,
					},
					{
						fieldname: "delivery_date",
						fieldtype: "Date",
						label: __("Customer Delivery Date"),
						default: frappe.datetime.add_days(
							frm.doc.expected_closure_date || frappe.datetime.get_today(),
							60,
						),
						reqd: 1,
					},
				],
				primary_action_label: __("Create or Open"),
				async primary_action(values) {
					const primaryButton = dialog.get_primary_btn();
					primaryButton.prop("disabled", true);
					try {
						const response = await frappe.call({
							method: "autoflow_360.api.project.convert_deal",
							type: "POST",
							args: {
								deal_name: frm.doc.name,
								company: values.company,
								customer: values.customer,
								product_family: values.product_family,
								delivery_date: values.delivery_date,
							},
							freeze: true,
							freeze_message: __("Creating customer project..."),
						});
						if (response.message) {
							dialog.hide();
							frappe.set_route("Form", "Customer Project", response.message);
						}
					} finally {
						primaryButton.prop("disabled", false);
					}
				},
			});
			dialog.show();
		});
	},
});
