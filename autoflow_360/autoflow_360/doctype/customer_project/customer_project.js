frappe.ui.form.on("Customer Project", {
	refresh(frm) {
		const colors = {
			"潜在项目": "blue",
			"样品阶段": "cyan",
			"报价阶段": "orange",
			"已定点": "green",
			"订单履约": "blue",
			"已交付": "green",
			"待回款": "orange",
			"已结项": "green",
			"暂停": "yellow",
			"失败": "red",
			"取消": "gray",
		};
		if (!frm.is_new() && frm.doc.stage) {
			frm.page.set_indicator(__(frm.doc.stage), colors[frm.doc.stage] || "gray");
		}
	},
});
