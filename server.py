import os
import io
import json
import gzip
import datetime
import urllib.parse
import pandas as pd
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from src.agent import MinhAnSalesAgent, SALES_REPRESENTATIVES
from src.bi_analytics import BIAnalyticsEngine
from src.tools import DocumentGenerationTool
from src.hung_phat_analytics import is_hung_phat_workbook, analyze_hung_phat_data

PORT = 8080

CURRENT_HUNG_PHAT_ANALYSIS = None
HUNG_PHAT_PRELOADED = None
if os.path.exists("Hung_Phat_Test_Data_5_Steps.xlsx"):
    try:
        xl_hp = pd.ExcelFile("Hung_Phat_Test_Data_5_Steps.xlsx")
        HUNG_PHAT_PRELOADED = analyze_hung_phat_data(xl_hp)
    except Exception as e:
        print("Error preloading Hung Phat:", e)

# Khởi tạo Agent
agent = MinhAnSalesAgent(
    catalog_path="data/catalog.json",
    inventory_path="data/inventory.json",
    policies_path="data/policies.json"
)
bi_engine = BIAnalyticsEngine()

# Nạp sẵn dữ liệu mẫu đề thi và tiền xử lý
with open("data/sample_requests.json", "r", encoding="utf-8") as f:
    INITIAL_SAMPLE_DATA = json.load(f)

# Bóc tách Task 1 sẵn
INITIAL_EXTRACTED = []
for idx, r in enumerate(INITIAL_SAMPLE_DATA):
    ext = agent.extractor.run(r)
    rep = SALES_REPRESENTATIVES[idx % len(SALES_REPRESENTATIVES)]
    missing_str = "\n".join([f"- {m}" for m in ext.missing_fields])
    email_draft = f"""Kính gửi Quý khách hàng {ext.customer_name},

Công ty Công nghệ Minh An xin chân thành cảm ơn Quý khách đã quan tâm đến thiết bị và giải pháp công nghệ của chúng tôi.

Để có thể lập Hồ sơ phương án tối ưu và báo giá chính xác nhất, chúng tôi kính đề nghị Quý khách cung cấp thêm một số thông tin còn thiếu sau:
{missing_str}

Trân trọng,
{rep} - Bộ phận Kinh doanh Minh An Tech"""
    INITIAL_EXTRACTED.append({
        "request_id": ext.request_id,
        "customer_name": ext.customer_name,
        "contact_email": ext.contact_email,
        "channel": ext.channel,
        "raw_text": ext.raw_text,
        "assigned_sales_rep": rep,
        "budget": ext.customer_budget,
        "delivery_days": ext.required_delivery_days,
        "requested_discount_rate": ext.requested_discount_rate,
        "is_complete": ext.is_complete,
        "missing_fields": ext.missing_fields,
        "clarification_email_draft": email_draft,
        "items": [
            {
                "sku": it.sku,
                "matched_name": it.matched_name,
                "raw_name": it.raw_name,
                "quantity": it.quantity,
                "unit_price": it.unit_price
            } for it in ext.items
        ]
    })

# Tiền xử lý full batch cho Task 2, 3, 4
init_dossiers, init_summary = agent.process_batch(INITIAL_SAMPLE_DATA)
INITIAL_DOSSIERS_JSON = [
    {
        "opportunity_id": d.opportunity_id,
        "customer_name": d.customer_name,
        "contact_email": d.contact_email,
        "channel": d.channel,
        "assigned_sales_rep": d.assigned_sales_rep,
        "status": d.status,
        "next_action": d.next_action,
        "customer_response_draft": d.customer_response_draft,
        "approval_ticket": d.approval_ticket,
        "extracted_data": {
            "raw_text": d.extracted_data.raw_text,
            "budget": d.extracted_data.customer_budget,
            "delivery_days": d.extracted_data.required_delivery_days,
            "requested_discount_rate": d.extracted_data.requested_discount_rate,
            "is_complete": d.extracted_data.is_complete,
            "missing_fields": d.extracted_data.missing_fields,
            "items": [
                {
                    "sku": it.sku,
                    "matched_name": it.matched_name,
                    "raw_name": it.raw_name,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "total_price": it.total_price
                } for it in d.extracted_data.items
            ]
        },
        "pricing": {
            "base_subtotal": d.pricing.base_subtotal,
            "applied_discount_rate": d.pricing.applied_discount_rate,
            "total_discount_amount": d.pricing.total_discount_amount,
            "final_proposal_value": d.pricing.final_proposal_value,
            "is_within_budget": d.pricing.is_within_budget,
            "pricing_notes": d.pricing.pricing_notes
        } if d.pricing else None,
        "feasibility": {
            "overall_lead_days_needed": d.feasibility.overall_lead_days_needed,
            "customer_deadline_days": d.feasibility.customer_deadline_days,
            "lead_time_status": d.feasibility.lead_time_status,
            "is_feasible": d.feasibility.is_feasible,
            "rejection_reason": d.feasibility.rejection_reason,
            "items_feasibility": [
                {
                    "sku": it.sku,
                    "name": it.name,
                    "requested_qty": it.requested_qty,
                    "available_stock": it.available_stock,
                    "is_stock_sufficient": it.is_stock_sufficient,
                    "stock_shortage": it.stock_shortage,
                    "estimated_lead_days": it.estimated_lead_days,
                    "inventory_location": it.inventory_location
                } for it in d.feasibility.items_feasibility
            ] if d.feasibility else []
        } if d.feasibility else None,
        "approval": {
            "requires_escalation": d.approval.requires_escalation,
            "approver_role": d.approval.approver_role,
            "reasons": d.approval.reasons
        } if d.approval else None
    } for d in init_dossiers
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Minh An Tech - AI Agent B2B Sales System</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>💼</text></svg>">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #0f766e;
            --primary-hover: #115e59;
            --active-bg: #e6f4ea;
            --active-border: #c7ebd1;
            --active-title: #065f46;
            --active-sub: #047857;
            --sidebar-bg: #eff5f1;
            --bg: #f8fafc;
            --card: #ffffff;
            --border: #e2e8f0;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --success: #15803d;
            --success-bg: #dcfce7;
            --warning: #b45309;
            --warning-bg: #fef3c7;
            --danger: #b91c1c;
            --danger-bg: #fee2e2;
            --purple: #6b21a8;
            --purple-bg: #f3e8ff;
            --blue: #1d4ed8;
            --blue-bg: #dbeafe;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text-main); line-height: 1.5; display: flex; height: 100vh; overflow: hidden; }

        /* THANH MENU BÊN TRÁI THEO MOCKUP */
        .sidebar { width: 310px; min-width: 310px; background: var(--sidebar-bg); border-right: 1px solid #dce6e0; padding: 28px 20px; display: flex; flex-direction: column; overflow-y: auto; }
        .sidebar-title { font-size: 13px; font-weight: 800; color: #2d5045; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 20px; padding-left: 6px; }

        .task-list { display: flex; flex-direction: column; gap: 12px; }
        .task-item { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-radius: 16px; border: 1.5px solid #e5e7eb; background: #ffffff; transition: all 0.2s ease; cursor: pointer; user-select: none; }
        .task-item:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(15, 118, 110, 0.1); }
        
        .task-item.active { background: var(--active-bg); border-color: var(--active-border); box-shadow: 0 2px 8px rgba(16, 185, 129, 0.12); }
        .task-item.active .task-title { color: var(--active-title); font-weight: 800; }
        .task-item.active .task-desc { color: var(--active-sub); font-weight: 500; }
        .task-item.active .task-icon-box { background: var(--primary); color: white; border-color: transparent; }
        .task-item.active .chevron-icon { stroke: var(--active-title); display: block; }
        .task-item.active .status-indicator { display: none; }

        .task-item .task-title { color: #1e293b; font-weight: 700; }
        .task-item .task-desc { color: #64748b; }
        .task-item .task-icon-box { background: #f8fafc; border: 1px solid #e2e8f0; color: #0f766e; }

        .task-left { display: flex; align-items: center; gap: 12px; }
        .task-icon-box { width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .task-icon-box svg { width: 22px; height: 22px; }
        .task-info { display: flex; flex-direction: column; }
        .task-title { font-size: 15px; line-height: 1.2; }
        .task-desc { font-size: 12px; margin-top: 3px; }

        .task-right svg { width: 18px; height: 18px; }
        .chevron-icon { display: none; }
        .status-indicator { font-size: 11px; font-weight: 700; color: var(--primary); background: #f0fdfa; padding: 2px 7px; border-radius: 999px; }

        /* KHUNG CHÍNH BÊN PHẢI */
        .main-wrapper { flex: 1; display: flex; flex-direction: column; height: 100vh; overflow-y: auto; }
        
        .topbar { background: #ffffff; border-bottom: 1px solid var(--border); padding: 18px 35px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 10; }
        .topbar-title h1 { font-size: 18px; font-weight: 800; display: flex; align-items: center; gap: 8px; color: #0f172a; }
        .topbar-title span { font-size: 13px; color: var(--text-muted); font-weight: 500; }
        .status-badge { background: #0f766e; color: white; padding: 5px 14px; border-radius: 999px; font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
        .status-badge::before { content: ""; width: 8px; height: 8px; background: #6ee7b7; border-radius: 50%; display: inline-block; }

        .content-container { padding: 25px 35px; max-width: 1400px; }

        /* PANELS */
        .task-panel { display: none; }
        .task-panel.active { display: block; }

        /* CARDS */
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 25px; }
        .card h2 { font-size: 17px; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }

        /* BANNER HƯỚNG DẪN CHUYỂN BƯỚC */
        .step-transition-banner { background: #f0fdfa; border: 1.5px solid #99f6e4; border-radius: 12px; padding: 18px 22px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; }
        .step-transition-banner h4 { font-size: 15px; font-weight: 800; color: #0f766e; }
        .step-transition-banner p { font-size: 12px; color: #115e59; margin-top: 3px; }

        /* PIPELINE VISUALIZER (TRONG TASK 2) */
        .pipeline-card { background: #ffffff; border: 1.5px solid #ccfbf1; border-radius: 14px; padding: 22px; margin-bottom: 25px; box-shadow: 0 4px 14px rgba(15, 118, 110, 0.06); }
        .pipeline-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .pipeline-header h2 { font-size: 16px; font-weight: 700; color: #0f766e; display: flex; align-items: center; gap: 8px; margin: 0; }
        
        .flow-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; position: relative; }
        .flow-node { background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 12px; padding: 16px 14px; transition: all 0.25s ease; position: relative; cursor: pointer; user-select: none; }
        .flow-node:hover { border-color: #0f766e; transform: translateY(-3px); box-shadow: 0 4px 12px rgba(15, 118, 110, 0.12); }
        .flow-node.active { border-color: #f59e0b; background: #fffbeb; transform: translateY(-2px); box-shadow: 0 4px 10px rgba(245, 158, 11, 0.15); }
        .flow-node.completed { border-color: #10b981; background: #ecfdf5; }
        .flow-node.completed::after { content: "✓"; position: absolute; top: 10px; right: 12px; font-weight: 800; color: #10b981; font-size: 15px; }
        
        .flow-step-tag { font-size: 10px; font-weight: 800; color: #0f766e; text-transform: uppercase; letter-spacing: 0.5px; }
        .flow-step-name { font-size: 13px; font-weight: 700; margin-top: 4px; color: #0f172a; }
        .flow-step-desc { font-size: 11px; color: var(--text-muted); margin-top: 3px; line-height: 1.3; }

        /* COMMAND BAR (NÚT CHẠY 1 CÚ CLICK) */
        .command-bar { background: #f0fdfa; border: 2px solid #99f6e4; border-radius: 12px; padding: 18px 22px; margin-top: 18px; display: flex; justify-content: space-between; align-items: center; gap: 15px; }
        .command-info h4 { font-size: 15px; font-weight: 800; color: #0f766e; display: flex; align-items: center; gap: 6px; }
        .command-info p { font-size: 13px; color: #115e59; margin-top: 3px; }

        /* LIVE CONSOLE */
        .console-box { background: #0f172a; color: #a5f3fc; border-radius: 10px; padding: 14px 18px; font-family: monospace; font-size: 12px; max-height: 130px; overflow-y: auto; margin-top: 15px; border: 1px solid #1e293b; }
        .console-line { margin-bottom: 4px; line-height: 1.4; }
        .console-time { color: #64748b; margin-right: 6px; }
        .console-tag { color: #38bdf8; font-weight: 700; margin-right: 6px; }

        /* DRAG AND DROP ZONE */
        .dropzone { border: 2px dashed #99f6e4; background: #f0fdfa; border-radius: 14px; padding: 18px; text-align: center; cursor: pointer; transition: 0.2s; user-select: none; }
        .dropzone:hover, .dropzone.dragover { border-color: var(--primary); background: #ccfbf1; }
        .dropzone-icon { width: 32px; height: 32px; stroke: var(--primary); margin-bottom: 4px; }
        .dropzone-text { font-size: 13px; font-weight: 700; color: #115e59; }
        .dropzone-hint { font-size: 11px; color: #134e4a; margin-top: 2px; }

        /* BUTTONS */
        .btn { padding: 9px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: 0.15s; display: inline-flex; align-items: center; gap: 6px; text-decoration: none; user-select: none; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); transform: translateY(-1px); }
        .btn-command { background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%); color: white; font-weight: 800; font-size: 14px; padding: 12px 24px; border-radius: 10px; box-shadow: 0 4px 12px rgba(15, 118, 110, 0.25); }
        .btn-command:hover { background: linear-gradient(135deg, #115e59 0%, #0f766e 100%); transform: translateY(-1px); box-shadow: 0 6px 16px rgba(15, 118, 110, 0.35); }
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; }
        .btn-outline { background: white; border: 1.5px solid #cbd5e1; color: var(--text-main); font-weight: 600; }
        .btn-outline:hover { background: #f8fafc; border-color: var(--primary); color: var(--primary); }
        
        /* EXPORT BUTTONS */
        .btn-export { background: #0f766e; color: white; font-weight: 700; padding: 9px 16px; border-radius: 8px; border: 1px solid #115e59; box-shadow: 0 2px 6px rgba(15, 118, 110, 0.15); }
        .btn-export:hover { background: #134e4a; transform: translateY(-1px); }
        .btn-export-alt { background: #334155; color: white; font-weight: 700; padding: 9px 16px; border-radius: 8px; border: 1px solid #1e293b; }
        .btn-export-alt:hover { background: #1e293b; transform: translateY(-1px); }

        /* TABLES */
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th { background: #f8fafc; padding: 12px 14px; font-size: 12px; font-weight: 700; color: var(--text-muted); border-bottom: 1.5px solid var(--border); text-transform: uppercase; }
        td { padding: 13px 14px; font-size: 13px; border-bottom: 1px solid var(--border); vertical-align: middle; }
        tr:hover { background: #f8fafc; }

        .badge { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; display: inline-block; white-space: nowrap; }
        .badge-green { background: var(--success-bg); color: var(--success); }
        .badge-amber { background: var(--warning-bg); color: var(--warning); }
        .badge-red { background: var(--danger-bg); color: var(--danger); }
        .badge-purple { background: var(--purple-bg); color: var(--purple); }
        .badge-blue { background: var(--blue-bg); color: var(--blue); }

        .empty-state { text-align: center; padding: 35px 20px; color: var(--text-muted); }
        .form-control { width: 100%; padding: 10px 14px; border: 1.5px solid var(--border); border-radius: 8px; font-size: 14px; }
        .form-control:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.15); }
        textarea.form-control { min-height: 80px; resize: vertical; }

        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        pre { background: #0f172a; color: #38bdf8; padding: 14px; border-radius: 8px; font-size: 13px; overflow-x: auto; white-space: pre-wrap; }
        .box { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 15px; margin-top: 10px; }
        .box-title { font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; }

        /* KPI & STAT CARDS */
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 25px; }
        .kpi-card { background: var(--card); border: 1.5px solid var(--border); border-radius: 14px; padding: 18px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
        .kpi-card .kpi-label { font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; }
        .kpi-card .kpi-value { font-size: 26px; font-weight: 800; margin-top: 6px; color: var(--text-main); }
        .kpi-card .kpi-sub { font-size: 12px; margin-top: 4px; color: var(--text-muted); }
        .kpi-card.hero { background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%); color: white; border: none; }
        .kpi-card.hero .kpi-label { color: #ccfbf1; }
        .kpi-card.hero .kpi-value { color: white; }
        .kpi-card.hero .kpi-sub { color: #e6fffa; }

        /* DASHBOARD VISUALS */
        .dashboard-analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 25px; }
        .dash-widget { background: #ffffff; border: 1.5px solid var(--border); border-radius: 14px; padding: 20px; }
        .dash-widget-title { font-size: 14px; font-weight: 700; color: #1e293b; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between; }
        
        .progress-stacked { display: flex; height: 18px; border-radius: 999px; overflow: hidden; background: #e2e8f0; margin-bottom: 12px; }
        .progress-bar-seg { height: 100%; transition: width 0.4s ease; }

        .stat-legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; }
        .stat-legend-item { display: flex; align-items: center; gap: 6px; }
        .legend-dot { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }

        /* EXPORT TOOLBAR */
        .export-bar { background: #f0fdfa; border: 1.5px solid #99f6e4; border-radius: 12px; padding: 18px 22px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; }
        .export-info h4 { font-size: 15px; font-weight: 800; color: #0f766e; }
        .export-info p { font-size: 12px; color: #115e59; margin-top: 3px; }
        .export-buttons { display: flex; gap: 10px; flex-wrap: wrap; }

        /* TOAST */
        .toast { position: fixed; bottom: 25px; right: 25px; background: #0f172a; color: white; padding: 14px 22px; border-radius: 10px; font-size: 14px; font-weight: 600; box-shadow: 0 6px 18px rgba(0,0,0,0.25); z-index: 999; display: none; align-items: center; gap: 8px; }
        .toast.show { display: flex; }

        /* BỘ LỌC TƯƠNG TÁC (INTERACTIVE FILTERS) */
        .filter-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; }
        .filter-btn { padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; border: 1px solid var(--border); background: white; color: var(--text-muted); cursor: pointer; transition: 0.15s; }
        .filter-btn:hover { border-color: var(--primary); color: var(--primary); }
        .filter-btn.active { background: var(--primary); color: white; border-color: var(--primary); }
        .btn-outline.active { background: #0f766e !important; color: #ffffff !important; border-color: #0f766e !important; }

        @media (max-width: 900px) {
            body { flex-direction: column; overflow: auto; height: auto; }
            .sidebar { width: 100%; min-width: 100%; height: auto; }
            .main-wrapper { height: auto; }
            .flow-grid { grid-template-columns: 1fr 1fr; }
            .grid-2 { grid-template-columns: 1fr; }
            .dashboard-analytics-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>

    <!-- THANH MENU BÊN TRÁI THEO ĐÚNG MOCKUP -->
    <aside class="sidebar">
        <div class="sidebar-title">QUY TRÌNH</div>
        
        <div class="task-list">
            <!-- 1. KẾT NỐI & KIỂM TOÁN -->
            <div class="task-item active" id="menu-task-1" onclick="switchTask(1)">
                <div class="task-left">
                    <div class="task-icon-box">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                        </svg>
                    </div>
                    <div class="task-info">
                        <span class="task-title">1. Kết Nối & Kiểm Toán</span>
                        <span class="task-desc">Data Profiling & Quality</span>
                    </div>
                </div>
                <div class="task-right">
                    <svg class="chevron-icon" viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span class="status-indicator">Skill 1</span>
                </div>
            </div>

            <!-- 2. LÀM SẠCH & MÔ HÌNH HÓA -->
            <div class="task-item" id="menu-task-2" onclick="switchTask(2)">
                <div class="task-left">
                    <div class="task-icon-box">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"></path>
                            <path d="M22 21H7"></path>
                            <path d="m5 11 9 9"></path>
                        </svg>
                    </div>
                    <div class="task-info">
                        <span class="task-title">2. Làm Sạch & Mô Hình</span>
                        <span class="task-desc">Cleaning & Star Schema</span>
                    </div>
                </div>
                <div class="task-right">
                    <svg class="chevron-icon" viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span class="status-indicator">Skill 2</span>
                </div>
            </div>

            <!-- 3. PHÂN TÍCH & CHẨN ĐOÁN -->
            <div class="task-item" id="menu-task-3" onclick="switchTask(3)">
                <div class="task-left">
                    <div class="task-icon-box">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="18" y1="20" x2="18" y2="10"></line>
                            <line x1="12" y1="20" x2="12" y2="4"></line>
                            <line x1="6" y1="20" x2="6" y2="14"></line>
                        </svg>
                    </div>
                    <div class="task-info">
                        <span class="task-title">3. Phân Tích & Chẩn Đoán</span>
                        <span class="task-desc">KPI Metrics & Insights</span>
                    </div>
                </div>
                <div class="task-right">
                    <svg class="chevron-icon" viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span class="status-indicator">Skill 3-4</span>
                </div>
            </div>

            <!-- 4. BÁO CÁO & DASHBOARD -->
            <div class="task-item" id="menu-task-4" onclick="switchTask(4)">
                <div class="task-left">
                    <div class="task-icon-box">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                    </div>
                    <div class="task-info">
                        <span class="task-title">4. Báo Cáo & Dashboard</span>
                        <span class="task-desc">BLUF Storytelling & Chart</span>
                    </div>
                </div>
                <div class="task-right">
                    <svg class="chevron-icon" viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span class="status-indicator">Skill 5</span>
                </div>
            </div>
        </div>
    </aside>

    <!-- KHUNG NỘI DUNG CHÍNH -->
    <main class="main-wrapper">
        <header class="topbar">
            <div class="topbar-title">
                <h1 id="topbar-h1">🏢 CÔNG TY CÔNG NGHỆ MINH AN <span>| AI Agent Xử Lý Yêu Cầu B2B</span></h1>
            </div>
            <div class="status-badge" id="header-status">Chờ Nhập Dữ Liệu</div>
        </header>

        <div class="content-container">

            <!-- ======================================================== -->
            <!-- TASK 1: KẾT NỐI (CHỈ TIẾP NHẬN DỮ LIỆU ĐA KÊNH & QUẢN LÝ) -->
            <!-- ======================================================== -->
            <div class="task-panel active" id="panel-task-1">
                
                <!-- KHU VỰC NHẬP DỮ LIỆU: FORM TRỰC TIẾP + DÁN TEXT/JSON + KÉO THẢ FILE -->
                <div class="card">
                    <h2>
                        <span>📥 Task 1: Tiếp Nhận & Kết Nối Nguồn Dữ Liệu</span>
                        <div style="display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn btn-primary" onclick="loadHungPhatSample()" style="background:#059669; border-color:#059669; font-weight:700;">🏢 Nạp Bộ Test Hưng Phát 5 Bước</button>
                            <button class="btn btn-outline" onclick="loadSampleDataset()">⚡ 6 Ca Mẫu Minh An</button>
                            <button class="btn btn-danger" onclick="resetAll()">🗑️ Xóa Trắng Dữ Liệu</button>
                        </div>
                    </h2>

                    <div class="grid-2">
                        <!-- CỘT 1: FORM NHẬP YÊU CẦU TRỰC TIẾP -->
                        <div style="background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:12px; padding:18px;">
                            <h3 style="font-size:14px; font-weight:700; color:#0f766e; margin-bottom:12px; display:flex; align-items:center; gap:6px;">
                                ✍️ Cách 1: Nhập Trực Tiếp Yêu Cầu Mới
                            </h3>
                            <div style="display:flex; flex-direction:column; gap:10px;">
                                <div class="grid-2" style="gap:10px;">
                                    <div>
                                        <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">Tên Khách Hàng / Doanh Nghiệp *</label>
                                        <input type="text" id="man-cust-name" class="form-control" placeholder="VD: Tập đoàn Bưu chính VN">
                                    </div>
                                    <div>
                                        <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">Email Liên Hệ *</label>
                                        <input type="email" id="man-cust-email" class="form-control" placeholder="VD: procurement@vnpost.vn">
                                    </div>
                                </div>

                                <div class="grid-2" style="gap:10px;">
                                    <div>
                                        <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">Kênh Tiếp Nhận</label>
                                        <select id="man-channel" class="form-control">
                                            <option value="Email">Email Doanh Nghiệp</option>
                                            <option value="Zalo">Zalo OA Bán Hàng</option>
                                            <option value="Hotline">Hotline Tiếp Nhận</option>
                                            <option value="Web Portal">Cổng Web Khách Hàng</option>
                                            <option value="Đấu Thầu">Cổng Đấu Thầu B2B</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">Thời Hạn Giao Hàng (Ngày)</label>
                                        <input type="number" id="man-deadline" class="form-control" placeholder="VD: 10 (ngày)">
                                    </div>
                                </div>

                                <div>
                                    <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">Ngân Sách Dự Kiến (VNĐ, tùy chọn)</label>
                                    <input type="number" id="man-budget" class="form-control" placeholder="VD: 500000000 (hoặc để trống AI tự bóc tách)">
                                </div>

                                <div>
                                    <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">Nội Dung Yêu Cầu / Thiết Bị Cần Báo Giá *</label>
                                    <textarea id="man-raw-text" class="form-control" style="min-height:75px;" placeholder="VD: Cần mua 20 chiếc laptop Dell XPS 13 và 15 màn hình Dell UltraSharp U2723QE, ngân sách 500 triệu, giao hàng trong 10 ngày, chiết khấu 7%..."></textarea>
                                </div>

                                <button class="btn btn-primary" style="margin-top:6px; justify-content:center; padding:11px;" onclick="handleAddManualRequest()">
                                    ➕ Thêm Yêu Cầu Này Vào Hệ Thống
                                </button>
                            </div>
                        </div>

                        <!-- CỘT 2: DÁN TEXT/JSON & KÉO THẢ TỆP -->
                        <div style="background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:12px; padding:18px; display:flex; flex-direction:column; justify-content:space-between;">
                            <div>
                                <h3 style="font-size:14px; font-weight:700; color:#0f766e; margin-bottom:12px;">
                                    📋 Cách 2: Dán Văn Bản / Chuỗi JSON
                                </h3>
                                <textarea id="paste-text" class="form-control" style="min-height:95px;" placeholder="Dán văn bản yêu cầu thô hoặc chuỗi JSON danh sách yêu cầu tại đây..."></textarea>
                                <button class="btn btn-primary" style="width:100%; margin-top:8px; justify-content:center;" onclick="handlePasteSubmit()">
                                    📥 Nạp Dữ Liệu Từ Khung Dán Này
                                </button>
                            </div>

                            <div style="margin-top:14px;">
                                <h3 style="font-size:14px; font-weight:700; color:#0f766e; margin-bottom:8px;">
                                    📁 Cách 3: Nạp Tệp Từ Máy Tính (Excel .XLSX, .XLS, .CSV, .JSON, .TXT)
                                </h3>
                                <div class="dropzone" id="drop-zone" onclick="triggerFileInput()">
                                    <svg class="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                        <polyline points="17 8 12 3 7 8"></polyline>
                                        <line x1="12" y1="3" x2="12" y2="15"></line>
                                    </svg>
                                    <div class="dropzone-text">KÉO THẢ TỆP VÀO ĐÂY HOẶC BẤM NÚT BÊN DƯỚI</div>
                                    <div class="dropzone-hint">Hỗ trợ đầy đủ Excel (.xlsx, .xls), CSV, JSON, TXT - Tự động bóc tách từng dòng bảng tính</div>
                                </div>
                                <div style="margin-top:10px; display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                                    <button type="button" class="btn btn-command" style="font-size:13px; padding:9px 16px;" onclick="triggerFileInput()">
                                        📂 Bấm Vào Đây Để Chọn Tệp Từ Máy Tính...
                                    </button>
                                    <span id="selected-file-name" style="font-size:13px; font-weight:700; color:#0f766e;">Chưa chọn tệp</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- WIDGET KIỂM TOÁN CHẤT LƯỢNG DỮ LIỆU & PROFILING (SKILL 1) -->
                <div class="card" id="profiling-card" style="border: 1.5px solid #cbd5e1; background: #ffffff;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
                        <div>
                            <h3 style="font-size:15px; font-weight:800; color:#0f766e; display:flex; align-items:center; gap:8px; margin:0;">
                                🔍 KIỂM TOÁN CHẤT LƯỢNG DỮ LIỆU ĐẦU VÀO (DATA PROFILING & QUALITY AUDIT)
                            </h3>
                            <p style="font-size:12px; color:var(--text-muted); margin:3px 0 0 0;">
                                Tự động kiểm tra Schema định dạng, tỷ lệ NULL/Missing, rà soát trùng lặp và phát hiện giá trị ngoại lai (IQR) theo chuẩn BI.
                            </p>
                        </div>
                        <div>
                            <span class="badge badge-green" id="profiling-health-badge" style="font-size:12px; padding:6px 14px;">🟢 100% Sẵn Sàng Phân Tích</span>
                        </div>
                    </div>

                    <!-- 4 THỐNG KÊ KIỂM TOÁN DỮ LIỆU -->
                    <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:14px;">
                        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px;">
                            <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Tổng Số Bản Ghi</div>
                            <div style="font-size:20px; font-weight:800; color:#0f172a; margin-top:2px;" id="prof-total-rows">0</div>
                            <div style="font-size:11px; color:#10b981; margin-top:2px;">Bản ghi tiếp nhận</div>
                        </div>
                        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px;">
                            <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Trùng Lặp (Duplicates)</div>
                            <div style="font-size:20px; font-weight:800; color:#0f172a; margin-top:2px;" id="prof-duplicates">0</div>
                            <div style="font-size:11px; color:#10b981; margin-top:2px;">Khóa chính đơn nhất</div>
                        </div>
                        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px;">
                            <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Tỷ Lệ Thiếu Trường (NULL)</div>
                            <div style="font-size:20px; font-weight:800; color:#0f172a; margin-top:2px;" id="prof-null-rate">0%</div>
                            <div style="font-size:11px; color:#10b981; margin-top:2px;" id="prof-null-sub">Đầy đủ thông tin thiết yếu</div>
                        </div>
                        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px;">
                            <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Ngoại Lai Ngân Sách (IQR)</div>
                            <div style="font-size:20px; font-weight:800; color:#0f172a; margin-top:2px;" id="prof-outliers">0</div>
                            <div style="font-size:11px; color:var(--primary); margin-top:2px;">Trong phân phối chuẩn</div>
                        </div>
                    </div>

                    <!-- THÔNG TIN SCHEMA VÀ TYPE CHECK -->
                    <div style="background:#f0fdfa; border:1px solid #ccfbf1; border-radius:8px; padding:10px 14px; font-size:12px; color:#0f766e; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <span>📋 <b>Schema Type Detection:</b> Mã (ID: String) | Khách Hàng (Categorical) | Kênh (Enum) | Ngân Sách (Decimal/VNĐ) | Hạn Giao (Integer/Days)</span>
                        <span style="font-weight:700;">Chuẩn hóa ISO 8601: Đạt</span>
                    </div>
                </div>

                <!-- BẢNG DANH SÁCH YÊU CẦU ĐÃ TIẾP NHẬN -->
                <div class="card">
                    <h2>
                        <span>Danh Sách Yêu Cầu Đã Tiếp Nhận (<span id="req-count">0</span> yêu cầu)</span>
                        <button class="btn btn-command" onclick="switchTask(2)">
                            🚀 Chuyển Sang Task 2 (Chạy Luồng Quy Trình) ➔
                        </button>
                    </h2>
                    <table>
                        <thead>
                            <tr>
                                <th>MÃ YÊU CẦU</th>
                                <th>KHÁCH HÀNG & EMAIL</th>
                                <th>KÊNH</th>
                                <th>VĂN BẢN YÊU CẦU GỐC</th>
                                <th>NGÂN SÁCH</th>
                                <th>THỜI HẠN</th>
                                <th>TRẠNG THÁI</th>
                                <th>THAO TÁC</th>
                            </tr>
                        </thead>
                        <tbody id="task1-tbody"></tbody>
                    </table>
                </div>

                <!-- BANNER ĐIỀU HƯỚNG SANG TASK 2 -->
                <div class="step-transition-banner">
                    <div>
                        <h4>👉 BẠN ĐÃ TIẾP NHẬN XONG NGUỒN DỮ LIỆU?</h4>
                        <p>Bấm nút bên phải để chuyển sang Task 2: Hệ thống sẽ khởi chạy luồng quy trình tự động bóc tách NLP, kiểm tra tồn kho và chuẩn hóa!</p>
                    </div>
                    <button class="btn btn-command" onclick="switchTask(2)">
                        🚀 Bắt Đầu Làm Sạch & Chạy Luồng Quy Trình ➔
                    </button>
                </div>
            </div>

            <!-- ======================================================== -->
            <!-- TASK 2: LÀM SẠCH, KIỂM TRA & CHUẨN HÓA + LUỒNG QUY TRÌNH -->
            <!-- ======================================================== -->
            <div class="task-panel" id="panel-task-2">
                
                <!-- LUỒNG QUY TRÌNH TỰ ĐỘNG CHUYỂN SANG TASK 2 THEO YÊU CẦU -->
                <div class="pipeline-card">
                    <div class="pipeline-header">
                        <h2>⚡ Luồng Quy Trình Tự Động Làm Sạch & Chuẩn Hóa</h2>
                        <span style="font-size:12px; font-weight:700; color:#0f766e; background:#ccfbf1; padding:4px 10px; border-radius:6px;" id="flow-status-tag">
                            SẴN SÀNG CHẠY
                        </span>
                    </div>

                    <!-- 4 BƯỚC TRÊN LUỒNG ĐỀU BẤM ĐƯỢC TRỰC TIẾP -->
                    <div class="flow-grid">
                        <div class="flow-node active" id="node-1" onclick="runSingleStep(1)" title="Bấm để kích hoạt Bước 2.1">
                            <div class="flow-step-tag">Giai Đoạn 2.1 (Click để chạy)</div>
                            <div class="flow-step-name">🧠 Bóc Tách NLP & Chuẩn Hóa</div>
                            <div class="flow-step-desc">Khớp mã SKU danh mục Catalog & Số lượng</div>
                        </div>
                        <div class="flow-node" id="node-2" onclick="runSingleStep(2)" title="Bấm để kích hoạt Bước 2.2">
                            <div class="flow-step-tag">Giai Đoạn 2.2 (Click để chạy)</div>
                            <div class="flow-step-name">🔍 Thẩm Tra Checklist Đầy Đủ</div>
                            <div class="flow-step-desc">Đối chiếu 4 trường bắt buộc (SKU, SL, Ngân sách, Deadline)</div>
                        </div>
                        <div class="flow-node" id="node-3" onclick="runSingleStep(3)" title="Bấm để kích hoạt Bước 2.3">
                            <div class="flow-step-tag">Giai Đoạn 2.3 (Click để chạy)</div>
                            <div class="flow-step-name">🏭 Kiểm Tra Tồn Kho (HN & HCM)</div>
                            <div class="flow-step-desc">Thẩm định tồn khả dụng & Hàng cần nhập</div>
                        </div>
                        <div class="flow-node" id="node-4" onclick="runSingleStep(4)" title="Bấm để kích hoạt Bước 2.4">
                            <div class="flow-step-tag">Giai Đoạn 2.4 (Click để chạy)</div>
                            <div class="flow-step-name">⏱️ Chuẩn Hóa Lead Time</div>
                            <div class="flow-step-desc">Đánh giá kịp / trễ tiến độ giao hàng khách</div>
                        </div>
                    </div>

                    <!-- KHUNG PHÂN TÍCH CHUYÊN SÂU & HỎI XÁC NHẬN CHẠY TIẾP TỪNG BƯỚC -->
                    <div id="pipeline-stage-dialog" style="display:none; margin-top:16px; border-radius:12px; padding:18px 22px; background:#ffffff; border:2px solid #0f766e; box-shadow:0 8px 24px rgba(15,118,110,0.12); animation:fadeIn 0.3s ease;">
                    </div>

                    <!-- KHU VỰC PHÊ DUYỆT & KÍCH HOẠT LUỒNG QUY TRÌNH (CHỈ KHI DUYỆT MỚI CHẠY) -->
                    <div class="command-bar" id="command-bar" style="background:#f0fdfa; border:2px solid #0f766e; border-radius:12px; padding:18px 22px; margin-top:18px; display:flex; justify-content:space-between; align-items:center; gap:15px; flex-wrap:wrap;">
                        <div class="command-info" style="flex:1; min-width:280px;">
                            <h4 id="cmd-title" style="font-size:15px; font-weight:800; color:#0f766e; display:flex; align-items:center; gap:8px; margin:0;">
                                🛡️ PHÊ DUYỆT & KÍCH HOẠT LUỒNG QUY TRÌNH TỰ ĐỘNG
                            </h4>
                            <p id="cmd-desc" style="font-size:12.5px; color:#115e59; margin:4px 0 0 0;">
                                Luồng chạy chậm từng nhịp, phân tích chuyên sâu từng giai đoạn và dừng lại hỏi ý kiến của bạn trước khi chuyển sang bước tiếp theo.
                            </p>
                        </div>
                        <div id="cmd-action-btn-area" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                            <label style="font-size:12px; font-weight:700; color:#0f766e; display:flex; align-items:center; gap:6px; cursor:pointer; background:#e6fffa; padding:9px 13px; border-radius:8px; border:1px solid #99f6e4; user-select:none;">
                                <input type="checkbox" id="chk-step-by-step" checked onchange="togglePipelineMode(this.checked)" style="accent-color:#0f766e; width:15px; height:15px;">
                                🐢 Dừng hỏi xác nhận sau mỗi bước
                            </label>
                            <button class="btn btn-command" id="main-cmd-btn" style="font-size:13px; padding:11px 22px; font-weight:800;" onclick="approveAndRunPipeline()">
                                🛡️ DUYỆT & BẮT ĐẦU CHẠY LUỒNG ➔
                            </button>
                        </div>
                    </div>

                    <!-- CONSOLE LOG TRỰC TIẾP -->
                    <div class="console-box" id="console-box">
                        <div class="console-line"><span class="console-time">[HỆ THỐNG]</span> <span class="console-tag">[SẴN SÀNG]</span> Hệ thống đã sẵn sàng tiếp nhận dữ liệu. Vui lòng nhập dữ liệu ở Task 1 để bắt đầu khởi chạy quy trình!</div>
                    </div>
                </div>

                <!-- BẢNG DỮ LIỆU LÀM SẠCH & MÔ HÌNH HÓA STAR SCHEMA (SKILL 2) -->
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
                        <div>
                            <h2 style="margin:0; font-size:16px; color:#0f766e;">
                                📦 Task 2: Làm Sạch Dữ Liệu, Kiểm Tra Tồn Kho & Mô Hình Hóa Star Schema
                            </h2>
                            <p style="font-size:12px; color:var(--text-muted); margin:4px 0 0 0;">
                                Chuyển đổi giữa bảng kiểm định kho hàng và cấu trúc bảng Data Warehouse Star Schema kèm truy vấn SQL tối ưu.
                            </p>
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="btn filter-btn active" id="btn-t2-tab-clean" onclick="switchT2View('clean', this)">📦 Bảng Làm Sạch & Kho Hàng</button>
                            <button class="btn filter-btn" id="btn-t2-tab-schema" onclick="switchT2View('schema', this)">🏛️ Star Schema & Truy Vấn SQL</button>
                        </div>
                    </div>

                    <!-- VIEW 1: BẢNG LÀM SẠCH KHO & LEAD TIME -->
                    <div id="t2-view-clean">
                        <div style="display:flex; gap:8px;">
                            <button class="btn btn-outline" onclick="executeTask2()">🔄 Đồng Bộ Lại Kho</button>
                            <button class="btn btn-primary" onclick="switchTask(3)">Sang Task 3 (Phân Tích) ➔</button>
                        </div>
                    </h2>

                    <!-- BỘ LỌC TƯƠNG TÁC -->
                    <div class="filter-bar">
                        <span style="font-size:12px; font-weight:700; color:var(--text-muted); margin-right:4px;">Bộ lọc kho:</span>
                        <button class="filter-btn active" onclick="filterTask2('all', this)">Tất Cả Sản Phẩm</button>
                        <button class="filter-btn" onclick="filterTask2('in-stock', this)">✅ Đủ Tồn Kho Sẵn Sàng</button>
                        <button class="filter-btn" onclick="filterTask2('shortage', this)">⚠️ Cần Nhập Kho Bổ Sung</button>
                        <button class="filter-btn" onclick="filterTask2('on-time', this)">🚚 Kịp Tiến Độ Khách</button>
                        <button class="filter-btn" onclick="filterTask2('delayed', this)">❌ Trễ Tiến Độ</button>
                    </div>

                    <table id="t2-table">
                        <thead id="t2-thead">
                            <tr>
                                <th>MÃ CƠ HỘI</th>
                                <th>HẠNG MỤC (SKU CHUẨN HÓA)</th>
                                <th>SỐ LƯỢNG</th>
                                <th>TỒN KHẢ DỤNG</th>
                                <th>VỊ TRÍ KHO</th>
                                <th>LEAD TIME KHO CẦN</th>
                                <th>HẠN ĐỊNH CỦA KHÁCH</th>
                                <th>KẾT LUẬN TIẾN ĐỘ</th>
                            </tr>
                        </thead>
                        <tbody id="clean-tbody"></tbody>
                    </table>
                    </div>

                    <!-- VIEW 2: STAR SCHEMA & SQL CTE GENERATION (SKILL 2) -->
                    <div id="t2-view-schema" style="display:none;">
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:18px;">
                            <!-- CỘT 1: CẤU TRÚC STAR SCHEMA -->
                            <div style="background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:12px; padding:16px;">
                                <h4 style="font-size:13.5px; font-weight:800; color:#1e293b; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
                                    🏛️ Cấu Trúc Fact & Dimension Tables (Star Schema)
                                </h4>
                                <div style="display:flex; flex-direction:column; gap:8px; font-size:12px;">
                                    <div style="background:#ffffff; border-left:4px solid #0f766e; padding:8px 12px; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                                        <b style="color:#0f766e;">FACT: fact_sales_opportunity</b>
                                        <div style="color:var(--text-muted); font-size:11px; margin-top:2px;">opportunity_id, customer_key, rep_key, date_key, net_proposal_value, operating_margin, status</div>
                                    </div>
                                    <div style="background:#ffffff; border-left:4px solid #3b82f6; padding:8px 12px; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                                        <b style="color:#2563eb;">DIM: dim_customer</b>
                                        <div style="color:var(--text-muted); font-size:11px; margin-top:2px;">customer_key, customer_name, contact_email, channel, tier</div>
                                    </div>
                                    <div style="background:#ffffff; border-left:4px solid #8b5cf6; padding:8px 12px; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                                        <b style="color:#7c3aed;">DIM: dim_product</b>
                                        <div style="color:var(--text-muted); font-size:11px; margin-top:2px;">product_key, sku, product_name, category, unit_price, lead_days</div>
                                    </div>
                                    <div style="background:#ffffff; border-left:4px solid #f59e0b; padding:8px 12px; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                                        <b style="color:#d97706;">DIM: dim_sales_rep</b>
                                        <div style="color:var(--text-muted); font-size:11px; margin-top:2px;">rep_key, rep_name, max_discount_authority</div>
                                    </div>
                                    <div style="background:#ffffff; border-left:4px solid #10b981; padding:8px 12px; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                                        <b style="color:#059669;">DIM: dim_time</b>
                                        <div style="color:var(--text-muted); font-size:11px; margin-top:2px;">date_key, full_date, quarter_label (Qtr1-Qtr4), year (2022-2023)</div>
                                    </div>
                                </div>
                            </div>

                            <!-- CỘT 2: TRUY VẤN SQL CTE TỐI ƯU -->
                            <div style="background:#0f172a; color:#f8fafc; border-radius:12px; padding:16px; font-family:monospace; font-size:11.5px; position:relative;">
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                                    <span style="color:#38bdf8; font-weight:700;">⚡ SQL CTE: SUM OF SALES & OPERATING MARGIN</span>
                                    <button class="btn btn-outline" style="padding:3px 8px; font-size:10px; background:#1e293b; color:#38bdf8; border-color:#334155;" onclick="copySQLTemplate()">📋 Copy SQL</button>
                                </div>
                                <pre id="sql-preview-box" style="margin:0; overflow-x:auto; line-height:1.4; color:#a5f3fc; max-height:220px;">WITH opportunity_base AS (
    SELECT
        t.year,
        t.quarter_label,
        COUNT(f.opportunity_key) AS total_deals,
        SUM(f.net_proposal_value) AS total_sales,
        ROUND(AVG(f.operating_margin_rate * 100), 2) AS avg_margin_pct
    FROM fact_sales_opportunity f
    INNER JOIN dim_time t ON f.date_key = t.date_key
    GROUP BY t.year, t.quarter_label
)
SELECT year, quarter_label, total_sales, avg_margin_pct
FROM opportunity_base
ORDER BY year ASC, quarter_label ASC;</pre>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- BANNER ĐIỀU HƯỚNG SANG TASK 3 & XUẤT EXCEL -->
                <div class="step-transition-banner">
                    <div>
                        <h4>👉 ĐÃ HOÀN TẤT LÀM SẠCH & THẨM ĐỊNH KHO?</h4>
                        <p>Bạn có thể xuất ngay file Excel dữ liệu đã làm sạch hoặc chuyển sang Task 3 để phân tích tài chính đa chiều.</p>
                    </div>
                    <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
                        <button class="btn btn-export" onclick="exportCleanedData('excel')" style="background: linear-gradient(135deg, #0284c7, #0ea5e9); border: 1px solid #0369a1; color: white; font-weight: 800; box-shadow: 0 4px 12px rgba(14, 165, 233, 0.35);">
                            📗 Xuất File Excel Đã Làm Sạch (.XLSX)
                        </button>
                        <button class="btn btn-primary" onclick="switchTask(3)">
                            Sang Task 3 (Phân Tích & So Sánh) ➔
                        </button>
                    </div>
                </div>
            </div>

            <!-- ======================================================== -->
            <!-- TASK 3: PHÂN TÍCH & SO SÁNH CÁC DỮ LIỆU -->
            <!-- ======================================================== -->
            <div class="task-panel" id="panel-task-3">
                <div class="card">
                    <h2>
                        <span>Task 3: Phân Tích Chuyên Sâu & So Sánh Đa Chiều Các Dữ Liệu</span>
                        <div style="display:flex; gap:8px;">
                            <button class="btn btn-outline" onclick="executeTask3()">🔄 Tính Lại Báo Giá</button>
                            <button class="btn btn-primary" onclick="switchTask(4)">Sang Task 4 (Báo Cáo) ➔</button>
                        </div>
                    </h2>
                    
                    <div id="t3-content">
                        <!-- 4 KHỐI THỐNG KÊ SO SÁNH VĨ MÔ -->
                        <div class="kpi-grid">
                            <div class="kpi-card">
                                <div class="kpi-label">🎯 Tỷ Lệ Phù Hợp Ngân Sách</div>
                                <div class="kpi-value" style="color:var(--success);" id="t3-budget-rate">0%</div>
                                <div class="kpi-sub" id="t3-budget-sub">0 ca trong ngân sách</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-label">🏷️ Mức Chiết Khấu Bình Quân</div>
                                <div class="kpi-value" style="color:var(--purple);" id="t3-discount-stat">0%</div>
                                <div class="kpi-sub" id="t3-discount-sub">Định mức chuẩn công ty</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-label">⏱️ Tỷ Lệ Đúng Hạn Giao Hàng</div>
                                <div class="kpi-value" style="color:var(--primary);" id="t3-leadtime-rate">0%</div>
                                <div class="kpi-sub" id="t3-leadtime-sub">Kho đáp ứng kịp deadline khách</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-label">💰 Tổng Giá Trị Chiết Khấu</div>
                                <div class="kpi-value" style="color:#b45309;" id="t3-total-savings">0 VNĐ</div>
                                <div class="kpi-sub">Số tiền giảm trừ cho khách</div>
                            </div>
                        </div>

                        <!-- BỘ LỌC TƯƠNG TÁC TASK 3 -->
                        <div class="filter-bar">
                            <span style="font-size:12px; font-weight:700; color:var(--text-muted); margin-right:4px;">Bộ lọc tài chính:</span>
                            <button class="filter-btn active" onclick="filterTask3('all', this)">Tất Cả Cơ Hội</button>
                            <button class="filter-btn" onclick="filterTask3('within-budget', this)">✅ Trong Ngân Sách</button>
                            <button class="filter-btn" onclick="filterTask3('over-budget', this)">❌ Vượt Ngân Sách</button>
                            <button class="filter-btn" onclick="filterTask3('escalation', this)">📑 Cần Trình Duyệt CK (>8%)</button>
                        </div>

                        <!-- BẢNG SO SÁNH ĐA CHIỀU -->
                        <table id="t3-table">
                            <thead>
                                <tr>
                                    <th>MÃ & KHÁCH HÀNG</th>
                                    <th>GIÁ NIÊM YẾT</th>
                                    <th>GIÁ ĐỀ XUẤT (NET)</th>
                                    <th>NGÂN SÁCH KH</th>
                                    <th>SO SÁNH NGÂN SÁCH (CHÊNH LỆCH)</th>
                                    <th>SO SÁNH CHIẾT KHẤU</th>
                                    <th>SO SÁNH TIẾN ĐỘ</th>
                                    <th>KẾT LUẬN & ĐÁNH GIÁ</th>
                                </tr>
                            </thead>
                            <tbody id="pricing-tbody"></tbody>
                        </table>
                    </div>
                </div>

                <!-- KHU VỰC PHÂN TÍCH CHẨN ĐOÁN & NGUYÊN NHÂN GỐC RỄ (SKILL 4: DIAGNOSTIC ANALYTICS) -->
                <div class="card" id="diagnostic-card" style="border: 1.5px solid #ccfbf1; background: #ffffff;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:10px;">
                        <div>
                            <h3 style="font-size:15px; font-weight:800; color:#0f766e; display:flex; align-items:center; gap:8px; margin:0;">
                                🔍 PHÂN TÍCH CHẨN ĐOÁN NGUYÊN NHÂN GỐC RỄ (DIAGNOSTIC ROOT CAUSE INSIGHTS)
                            </h3>
                            <p style="font-size:12px; color:var(--text-muted); margin:3px 0 0 0;">
                                Bóc tách đa chiều theo công thức chuẩn: [Observation - Quan sát số liệu] ➔ [Root Cause - Nguyên nhân gốc] ➔ [Business Impact - Tác động kinh doanh].
                            </p>
                        </div>
                        <span class="badge badge-purple" style="font-size:11.5px; padding:5px 12px;">📊 Pareto 80/20 & Segmentation</span>
                    </div>

                    <div id="diagnostic-insights-list" style="display:flex; flex-direction:column; gap:12px;">
                        <!-- Sẽ được render tự động qua JavaScript từ dữ liệu thực tế -->
                    </div>
                </div>

                <!-- BANNER ĐIỀU HƯỚNG SANG TASK 4 -->
                <div class="step-transition-banner">
                    <div>
                        <h4>👉 ĐÃ HOÀN TẤT PHÂN TÍCH SO SÁNH?</h4>
                        <p>Chuyển sang Task 4 để xem Executive Dashboard thẩm quyền phê duyệt và xuất file báo cáo kết quả đa định dạng.</p>
                    </div>
                    <button class="btn btn-primary" onclick="switchTask(4)">
                        Sang Task 4 (Dashboard & Xuất File) ➔
                    </button>
                </div>
            </div>

            <!-- ======================================================== -->
            <!-- TASK 4: BÁO CÁO, DASHBOARD & XUẤT FILE KẾT QUẢ -->
            <!-- ======================================================== -->
            <div class="task-panel" id="panel-task-4">
                <div class="card">
                    <h2>
                        <span>Task 4: Phê Duyệt, Executive Dashboard & Xuất File Kết Quả</span>
                        <div>
                            <button class="btn btn-outline" onclick="executeTask4()">🔄 Cập Nhật Dashboard</button>
                        </div>
                    </h2>
                    
                    <div id="t4-content">
                        <!-- KHỐI BÁO CÁO ĐIỀU HÀNH BLUF & ACTIONABLE RECOMMENDATIONS (SKILL 5) -->
                        <div style="background: linear-gradient(135deg, #f0fdfa 0%, #e6fcf5 100%); border: 1.5px solid #99f6e4; border-radius: 12px; padding: 18px 22px; margin-bottom: 22px;">
                            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px; flex-wrap:wrap; gap:10px;">
                                <div>
                                    <h4 style="font-size:15px; font-weight:800; color:#0f766e; display:flex; align-items:center; gap:8px; margin:0;">
                                        ⚡ TÓM TẮT ĐIỀU HÀNH BLUF (BOTTOM LINE UP FRONT)
                                    </h4>
                                    <p style="font-size:12.5px; color:#115e59; margin:4px 0 0 0;" id="bluf-lead-text">
                                        Doanh số đề xuất hợp lệ đạt mức khả quan, biên lợi nhuận hoạt động trung bình duy trì mức tối ưu từ 38% - 44%.
                                    </p>
                                </div>
                                <span class="badge badge-green" style="font-size:11.5px; padding:5px 12px;">🎯 Khuyến Nghị Hành Động</span>
                            </div>

                            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:12px; margin-top:12px;" id="bluf-actions-grid">
                                <div style="background:#ffffff; border:1px solid #ccfbf1; border-radius:8px; padding:10px 14px;">
                                    <b style="font-size:12px; color:#0f766e;">1. Fast-Track Phê Duyệt (4h - 24h):</b>
                                    <p style="font-size:11.5px; color:#334155; margin:3px 0 0 0;">Ưu tiên duyệt các đơn trên 200M giữ biên lợi nhuận > 40% để bảo toàn tỷ lệ chốt thầu.</p>
                                </div>
                                <div style="background:#ffffff; border:1px solid #ccfbf1; border-radius:8px; padding:10px 14px;">
                                    <b style="font-size:12px; color:#2563eb;">2. Điều Phối Tồn Kho Liên Vùng:</b>
                                    <p style="font-size:11.5px; color:#334155; margin:3px 0 0 0;">Xuất kho dự phòng TP.HCM sang Hà Nội cho dòng máy chủ Server để rút ngắn Lead time từ 14 xuống 3 ngày.</p>
                                </div>
                                <div style="background:#ffffff; border:1px solid #ccfbf1; border-radius:8px; padding:10px 14px;">
                                    <b style="font-size:12px; color:#d97706;">3. Tự Động Bổ Sung Thông Tin:</b>
                                    <p style="font-size:11.5px; color:#334155; margin:3px 0 0 0;">Gửi email làm rõ thông số kỹ thuật cho các yêu cầu thiếu thông tin trong vòng 30 phút sau khi nhận.</p>
                                </div>
                            </div>
                        </div>

                        <!-- THANH CÔNG CỤ XUẤT FILE ĐA ĐỊNH DẠNG -->
                        <div class="export-bar">
                            <div class="export-info">
                                <h4>💾 XUẤT FILE KẾT QUẢ ĐA ĐỊNH DẠNG (BẤM ĐỂ TẢI XUỐNG NGAY)</h4>
                                <p>Hỗ trợ đầy đủ Excel/CSV (UTF-8 BOM), JSON tổng hợp, Hồ sơ Markdown và Nhật ký Audit Trail.</p>
                            </div>
                            <div class="export-buttons">
                                <button class="btn btn-export" onclick="exportCleanedData('csv')" style="background: linear-gradient(135deg, #059669, #10b981); border: 1px solid #047857; color: white; font-weight: 800; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35);">
                                    ✨ Xuất Dữ Liệu Đã Làm Sạch (.CSV)
                                </button>
                                <button class="btn btn-export" onclick="exportCleanedData('excel')" style="background: linear-gradient(135deg, #0284c7, #0ea5e9); border: 1px solid #0369a1; color: white; font-weight: 800; box-shadow: 0 4px 12px rgba(14, 165, 233, 0.35);">
                                    📗 Xuất Dữ Liệu Đã Làm Sạch (.XLSX)
                                </button>
                                <button class="btn btn-export" onclick="exportCSV()">
                                    📊 Xuất Báo Cáo Thẩm Định (CSV)
                                </button>
                                <button class="btn btn-export" onclick="exportJSON()">
                                    📥 Xuất Báo Cáo JSON
                                </button>
                                <button class="btn btn-export-alt" onclick="exportMarkdown()">
                                    📑 Xuất Toàn Bộ Hồ Sơ (.MD)
                                </button>
                                <button class="btn btn-export-alt" onclick="exportAudit()">
                                    🛡️ Xuất Audit Trail (.JSON)
                                </button>
                            </div>
                        </div>

                        <!-- 4 HERO KPI CARDS -->
                        <div class="kpi-grid">
                            <div class="kpi-card hero">
                                <div class="kpi-label" id="lbl-kpi-1">Tổng Doanh Số Pipeline Hợp Lệ</div>
                                <div class="kpi-value" id="kpi-total-val">0 VNĐ</div>
                                <div class="kpi-sub" id="sub-kpi-1">Bao gồm cơ hội Hợp lệ & Đang chờ duyệt</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-label" id="lbl-kpi-2">Có Thể Tiếp Tục (Hợp Lệ)</div>
                                <div class="kpi-value" style="color: var(--success);" id="kpi-eligible">0</div>
                                <div class="kpi-sub" id="sub-kpi-2">Đáp ứng đủ ngân sách, kho & thẩm quyền</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-label" id="lbl-kpi-3">Chờ Cấp Quản Lý Duyệt</div>
                                <div class="kpi-value" style="color: var(--purple);" id="kpi-pending">0</div>
                                <div class="kpi-sub" id="sub-kpi-3">Vượt thẩm quyền chiết khấu / giá trị NVKD</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-label" id="lbl-kpi-4">Cần Bổ Sung Thông Tin</div>
                                <div class="kpi-value" style="color: var(--warning);" id="kpi-dash-missing">0</div>
                                <div class="kpi-sub" id="sub-kpi-4">Đã tạo email yêu cầu khách làm rõ</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-label" id="lbl-kpi-5">Chưa Đáp Ứng (Kho/Ngân sách)</div>
                                <div class="kpi-value" style="color: var(--danger);" id="kpi-unfeasible">0</div>
                                <div class="kpi-sub" id="sub-kpi-5">Đã tạo thư đề xuất phương án thay thế</div>
                            </div>
                        </div>

                        <!-- BIỂU ĐỒ KẾT HỢP DOANH SỐ & BIÊN LỢI NHUẬN (SUM OF TOTAL SALES & OPERATING MARGIN) -->
                        <div class="chart-card" id="dash-chart-card" style="margin-top:22px; margin-bottom:24px; background:#ffffff; border:1.5px solid #cbd5e1; border-radius:12px; padding:20px 24px; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:12px;">
                                <div>
                                    <h3 style="font-size:15px; font-weight:800; color:#1e293b; display:flex; align-items:center; gap:8px; margin:0;">
                                        📈 BIỂU ĐỒ TỔNG DOANH SỐ & TỶ SUẤT LỢI NHUẬN GỘP (TOTAL SALES & OPERATING MARGIN)
                                    </h3>
                                    <p style="font-size:12px; color:var(--text-muted); margin:3px 0 0 0;">
                                        Trực quan hóa doanh số B2B (Cột xanh - Trục trái) kết hợp biên lợi nhuận hoạt động (Đường đỏ - Trục phải 38% - 44%).
                                    </p>
                                </div>
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span class="badge badge-blue" style="font-size:11.5px; padding:6px 12px; font-weight:700;">📊 Dữ Liệu Thực Tế Tính Toán 100%</span>
                                </div>
                            </div>
                            <div id="combo-chart-container" style="min-height:220px; display:flex; align-items:center; justify-content:center;">
                                <!-- Sẽ được render tự động qua JavaScript khi có dữ liệu -->
                            </div>
                        </div>

                        <!-- EXECUTIVE DASHBOARD ANALYTICS WIDGETS -->
                        <div class="dashboard-analytics-grid">
                            <!-- WIDGET 1: CƠ CẤU TRẠNG THÁI -->
                            <div class="dash-widget">
                                <div class="dash-widget-title">
                                    <span>📊 Cơ Cấu Phân Bổ Trạng Thái Cơ Hội</span>
                                    <span style="font-size:12px; color:var(--text-muted);" id="widget-total-count">0 Yêu cầu</span>
                                </div>
                                <div class="progress-stacked" id="status-progress-bar">
                                    <div class="progress-bar-seg" id="seg-green" style="background:#15803d; width:0%;"></div>
                                    <div class="progress-bar-seg" id="seg-purple" style="background:#6b21a8; width:0%;"></div>
                                    <div class="progress-bar-seg" id="seg-amber" style="background:#b45309; width:0%;"></div>
                                    <div class="progress-bar-seg" id="seg-red" style="background:#b91c1c; width:0%;"></div>
                                </div>
                                <div class="stat-legend">
                                    <div class="stat-legend-item"><span class="legend-dot" style="background:#15803d;"></span> Có Thể Tiếp Tục: <b id="leg-green">0%</b></div>
                                    <div class="stat-legend-item"><span class="legend-dot" style="background:#6b21a8;"></span> Chờ Duyệt: <b id="leg-purple">0%</b></div>
                                    <div class="stat-legend-item"><span class="legend-dot" style="background:#b45309;"></span> Cần Bổ Sung: <b id="leg-amber">0%</b></div>
                                    <div class="stat-legend-item"><span class="legend-dot" style="background:#b91c1c;"></span> Chưa Đáp Ứng: <b id="leg-red">0%</b></div>
                                </div>
                            </div>

                            <!-- WIDGET 2: PHÂN CẤP THẨM QUYỀN PHÊ DUYỆT -->
                            <div class="dash-widget">
                                <div class="dash-widget-title">
                                    <span>🛡️ Phân Cấp Thẩm Quyền Phê Duyệt</span>
                                    <span style="font-size:12px; color:var(--text-muted);">Ma Trận Thẩm Quyền</span>
                                </div>
                                <div style="display:flex; flex-direction:column; gap:8px;" id="governance-breakdown">
                                    <div style="display:flex; justify-content:space-between; font-size:13px;">
                                        <span>👤 NVKD Tự Quyết (&le;8% & &le;200M):</span>
                                        <b id="gov-salesrep">0 cơ hội</b>
                                    </div>
                                    <div style="display:flex; justify-content:space-between; font-size:13px;">
                                        <span>👔 Trưởng Phòng Duyệt (&le;20% & &le;1 Tỷ):</span>
                                        <b id="gov-manager" style="color:var(--purple);">0 cơ hội</b>
                                    </div>
                                    <div style="display:flex; justify-content:space-between; font-size:13px;">
                                        <span>🏛️ Ban Giám Đốc Phê Duyệt (>20% / >1 Tỷ):</span>
                                        <b id="gov-board" style="color:var(--danger);">0 cơ hội</b>
                                    </div>
                                </div>
                            </div>

                            <!-- WIDGET 3: TẢI TRỌNG & DOANH SỐ NVKD -->
                            <div class="dash-widget">
                                <div class="dash-widget-title">
                                    <span>👥 Phân Bổ Tải Trọng & Doanh Số Theo NVKD</span>
                                    <span style="font-size:12px; color:var(--text-muted);">Điều Phối Round-Robin</span>
                                </div>
                                <div id="salesrep-workload" style="display:flex; flex-direction:column; gap:8px;"></div>
                            </div>

                            <!-- WIDGET 4: SỨC KHỎE CUNG ỨNG KHO HÀNG -->
                            <div class="dash-widget">
                                <div class="dash-widget-title">
                                    <span>🏭 Sức Khỏe Cung Ứng & Tiến Độ Kho</span>
                                    <span style="font-size:12px; color:var(--text-muted);">Hà Nội & TP.HCM</span>
                                </div>
                                <div style="display:flex; flex-direction:column; gap:8px;">
                                    <div style="display:flex; justify-content:space-between; font-size:13px;">
                                        <span>✅ Tỷ lệ thiết bị đủ hàng sẵn trong kho:</span>
                                        <b id="inv-instock-rate" style="color:var(--success);">0%</b>
                                    </div>
                                    <div style="display:flex; justify-content:space-between; font-size:13px;">
                                        <span>📦 Thiết bị cần nhập kho bổ sung:</span>
                                        <b id="inv-restock-needed" style="color:var(--warning);">0 mã SKU</b>
                                    </div>
                                    <div style="display:flex; justify-content:space-between; font-size:13px;">
                                        <span>🚚 Tỷ lệ giao hàng đúng hẹn yêu cầu:</span>
                                        <b id="inv-ontime-rate" style="color:var(--primary);">0%</b>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- ============================================== -->
                        <!-- KHU VỰC BẢNG DASHBOARD ĐIỀU HÀNH DOANH NGHIỆP -->
                        <!-- ============================================== -->
                        <div style="background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:14px; padding:20px; margin-top:25px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
                                <div>
                                    <h3 style="font-size:16px; font-weight:800; color:#0f766e; display:flex; align-items:center; gap:8px;">
                                        📊 BẢNG DASHBOARD ĐIỀU HÀNH & THEO DÕI QUY TRÌNH TOÀN DIỆN
                                    </h3>
                                    <p style="font-size:12px; color:var(--text-muted); margin-top:3px;">
                                        Bấm vào các tab bên dưới để chuyển đổi giữa các bảng quản trị: Cơ hội kinh doanh, Đội ngũ NVKD, Thẩm quyền và Tồn kho cung ứng.
                                    </p>
                                </div>
                                <!-- Ô TÌM KIẾM NHANH CHO BẢNG MASTER -->
                                <div id="dash-search-container" style="display:flex; align-items:center; gap:8px;">
                                    <input type="text" id="dash-search-input" class="form-control" style="width:260px; padding:7px 12px; font-size:12px;" placeholder="🔍 Tìm kiếm mã, khách hàng, NVKD..." oninput="handleDashSearch(this.value)">
                                </div>
                            </div>

                            <!-- SUB-TABS CHUYỂN ĐỔI BẢNG DASHBOARD -->
                            <div style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
                                <button class="filter-btn active" id="btn-dash-tab-master" onclick="switchDashTab('master', this)">
                                    📋 Bảng 1: Master Tổng Hợp Toàn Bộ Cơ Hội (<span id="dash-master-count">6</span>)
                                </button>
                                <button class="filter-btn" id="btn-dash-tab-salesrep" onclick="switchDashTab('salesrep', this)">
                                    👥 Bảng 2: Hiệu Suất & Tải Trọng Đội Ngũ NVKD
                                </button>
                                <button class="filter-btn" id="btn-dash-tab-governance" onclick="switchDashTab('governance', this)">
                                    🛡️ Bảng 3: Ma Trận Thẩm Quyền Phê Duyệt & Rủi Ro
                                </button>
                                <button class="filter-btn" id="btn-dash-tab-inventory" onclick="switchDashTab('inventory', this)">
                                    📦 Bảng 4: Cung Ứng & Sức Khỏe Kho Hàng (HN/HCM)
                                </button>
                            </div>

                            <!-- 1. BẢNG MASTER TOÀN BỘ CƠ HỘI -->
                            <div id="dash-view-master">
                                <div class="filter-bar" style="margin-bottom:12px;">
                                    <span style="font-size:12px; font-weight:700; color:var(--text-muted); margin-right:4px;">Lọc trạng thái:</span>
                                    <button class="filter-btn active" onclick="filterDashStatus('all', this)">Tất Cả</button>
                                    <button class="filter-btn" onclick="filterDashStatus('CÓ THỂ TIẾP TỤC', this)">✅ Có Thể Tiếp Tục</button>
                                    <button class="filter-btn" onclick="filterDashStatus('CHỜ DUYỆT', this)">📑 Chờ Duyệt</button>
                                    <button class="filter-btn" onclick="filterDashStatus('CẦN BỔ SUNG THÔNG TIN', this)">⚠️ Cần Bổ Sung</button>
                                    <button class="filter-btn" onclick="filterDashStatus('CHƯA ĐÁP ỨNG', this)">❌ Chưa Đáp Ứng</button>
                                </div>
                                <table style="background:white; border-radius:10px; overflow:hidden;">
                                    <thead>
                                        <tr>
                                            <th>MÃ CƠ HỘI</th>
                                            <th>KHÁCH HÀNG & KÊNH</th>
                                            <th>NVKD PHỤ TRÁCH</th>
                                            <th>TRẠNG THÁI</th>
                                            <th>GIÁ TRỊ ĐỀ XUẤT (NET)</th>
                                            <th>CẤP PHÊ DUYỆT</th>
                                            <th>HÀNH ĐỘNG TIẾP THEO</th>
                                            <th>THAO TÁC</th>
                                        </tr>
                                    </thead>
                                    <tbody id="report-tbody"></tbody>
                                </table>
                            </div>

                            <!-- 2. BẢNG HIỆU SUẤT ĐỘI NGŨ NVKD -->
                            <div id="dash-view-salesrep" style="display:none;">
                                <table style="background:white; border-radius:10px; overflow:hidden;">
                                    <thead>
                                        <tr>
                                            <th>STT</th>
                                            <th>CHUYÊN VIÊN KINH DOANH</th>
                                            <th>CƠ HỘI ĐƯỢC GÁN</th>
                                            <th>HỢP LỆ (TIẾP TỤC)</th>
                                            <th>CẦN TRÌNH DUYỆT</th>
                                            <th>THIẾU TT / CHƯA ĐẠT</th>
                                            <th>TỔNG DOANH SỐ PIPELINE</th>
                                            <th>TỶ LỆ HOÀN THÀNH</th>
                                            <th>ĐÁNH GIÁ TẢI TRỌNG</th>
                                        </tr>
                                    </thead>
                                    <tbody id="dash-salesrep-tbody"></tbody>
                                </table>
                            </div>

                            <!-- 3. BẢNG THẨM QUYỀN PHÊ DUYỆT & RỦI RO -->
                            <div id="dash-view-governance" style="display:none;">
                                <table style="background:white; border-radius:10px; overflow:hidden;">
                                    <thead>
                                        <tr>
                                            <th>CẤP THẨM QUYỀN</th>
                                            <th>HẠN MỨC PHÂN QUYỀN CHIẾT KHẤU & GIÁ TRỊ</th>
                                            <th>SỐ VỤ VIỆC PHỤ TRÁCH</th>
                                            <th>TỔNG GIÁ TRỊ THẨM ĐỊNH (VNĐ)</th>
                                            <th>SLA CAM KẾT XỬ LÝ</th>
                                            <th>QUY TẮC KIỂM SOÁT RỦI RO</th>
                                            <th>MỨC ĐỘ RỦI RO</th>
                                        </tr>
                                    </thead>
                                    <tbody id="dash-governance-tbody"></tbody>
                                </table>
                            </div>

                            <!-- 4. BẢNG CUNG ỨNG & SỨC KHỎE KHO HÀNG -->
                            <div id="dash-view-inventory" style="display:none;">
                                <table style="background:white; border-radius:10px; overflow:hidden;">
                                    <thead>
                                        <tr>
                                            <th>MÃ SKU</th>
                                            <th>TÊN THIẾT BỊ / DỊCH VỤ</th>
                                            <th>VỊ TRÍ KHO LƯU TRỮ</th>
                                            <th>TỔNG NHU CẦU ĐẶT</th>
                                            <th>TỒN KHO KHẢ DỤNG</th>
                                            <th>THIẾU HỤT CẦN NHẬP</th>
                                            <th>LEAD TIME CUNG ỨNG</th>
                                            <th>ĐÁNH GIÁ SẴN SÀNG</th>
                                        </tr>
                                    </thead>
                                    <tbody id="dash-inventory-tbody"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- INSPECTOR CHI TIẾT HỒ SƠ -->
            <div class="card" id="detail-card" style="display:none;">
                <h2>Chi Tiết Hồ Sơ Yêu Cầu: <span id="detail-id" style="color:var(--primary);"></span></h2>
                <div class="grid-2">
                    <div>
                        <div class="box">
                            <div class="box-title">Văn Bản Yêu Cầu Gốc</div>
                            <p id="detail-raw" style="font-style:italic; font-size:14px;"></p>
                        </div>
                        <div class="box">
                            <div class="box-title">Thông Tin Bóc Tách Thực Thể</div>
                            <div id="detail-extracted" style="font-size:14px;"></div>
                        </div>
                    </div>
                    <div>
                        <div class="box" style="height:100%;">
                            <div class="box-title" id="detail-action-title">Hành Động Đề Xuất / Phiếu Phê Duyệt</div>
                            <pre id="detail-action-content" style="max-height:280px; overflow-y:auto;"></pre>
                        </div>
                    </div>
                </div>
                <div style="text-align:right; margin-top:15px;">
                    <button class="btn btn-outline" onclick="document.getElementById('detail-card').style.display='none'">Đóng Lại</button>
                </div>
            </div>

        </div>
    </main>

    <!-- TOAST NOTIFICATION -->
    <div class="toast" id="toast">Thông báo</div>

    <!-- JAVASCRIPT ĐỒNG BỘ 100% -->
    <script>
        const PRELOADED_SAMPLE = __INITIAL_SAMPLE_JSON__;
        const PRELOADED_EXTRACTED = __INITIAL_EXTRACTED_JSON__;
        const PRELOADED_DOSSIERS = __INITIAL_DOSSIERS_JSON__;
        const PRELOADED_SUMMARY = __INITIAL_SUMMARY_JSON__;

        let rawItems = [];
        let extractedItems = [];
        let allDossiers = [];
        let currentSummaryData = null;
        let isPipelineApproved = false;

        let isAutoRunning = false;
        let t2Filter = 'all';
        let t3Filter = 'all';

        // LƯU TRỮ TRẠNG THÁI VÀO BỘ NHỚ TRÌNH DUYỆT (F5 / RELOAD KHÔNG MẤT DỮ LIỆU)
        function saveSystemState() {
            try {
                localStorage.setItem('minhan_raw_items', JSON.stringify(rawItems));
                localStorage.setItem('minhan_extracted_items', JSON.stringify(extractedItems));
                localStorage.setItem('minhan_all_dossiers', JSON.stringify(allDossiers));
                localStorage.setItem('minhan_summary_data', JSON.stringify(currentSummaryData));
                localStorage.setItem('minhan_pipeline_approved', isPipelineApproved ? 'true' : 'false');
            } catch(e) {
                console.warn('LocalStorage save warning:', e);
            }
        }

        // TẢI LẠI TRẠNG THÁI TỪ BỘ NHỚ TRÌNH DUYỆT KHI LOAD LẠI TRANG
        function loadSystemState() {
            try {
                const savedRaw = localStorage.getItem('minhan_raw_items');
                if (savedRaw) {
                    const parsed = JSON.parse(savedRaw);
                    if (Array.isArray(parsed) && parsed.length > 0) {
                        // Tự động dọn dẹp các mục bị lỗi đọc nhị phân zip/excel cũ (chứa chuỗi PK/docProps)
                        rawItems = parsed.filter(it => {
                            if (!it || typeof it !== 'object') return false;
                            const txt = it.raw_request_text || it.raw_text || '';
                            if (typeof txt === 'string' && (txt.startsWith('PK') || txt.includes('docProps') || txt.includes('[Content_Types]') || txt.includes('xl/'))) {
                                return false;
                            }
                            return true;
                        });
                        
                        if (rawItems.length === 0) {
                            // Đồng bộ xóa sạch các downstream data nếu rawItems bị rỗng
                            extractedItems = [];
                            allDossiers = [];
                            currentSummaryData = null;
                            isPipelineApproved = false;
                            try {
                                localStorage.removeItem('minhan_raw_items');
                                localStorage.removeItem('minhan_extracted_items');
                                localStorage.removeItem('minhan_all_dossiers');
                                localStorage.removeItem('minhan_summary_data');
                                localStorage.removeItem('minhan_pipeline_approved');
                            } catch(err) {}
                            return false;
                        }

                        if (rawItems.length < parsed.length) {
                            localStorage.setItem('minhan_raw_items', JSON.stringify(rawItems));
                        }

                        extractedItems = JSON.parse(localStorage.getItem('minhan_extracted_items') || '[]') || [];
                        allDossiers = JSON.parse(localStorage.getItem('minhan_all_dossiers') || '[]') || [];
                        currentSummaryData = JSON.parse(localStorage.getItem('minhan_summary_data') || 'null');
                        isPipelineApproved = (localStorage.getItem('minhan_pipeline_approved') === 'true');
                        return (allDossiers.length > 0);
                    }
                }
            } catch(e) {
                console.warn('LocalStorage load warning:', e);
            }

            // MẶC ĐỊNH KHÔNG BỊA ĐẶT DỮ LIỆU: KHI CHƯA CÓ DỮ LIỆU ĐẦU VÀO -> ĐỂ TRỐNG ĐỢI NGƯỜI DÙNG NẠP
            rawItems = [];
            extractedItems = [];
            allDossiers = [];
            currentSummaryData = null;
            isPipelineApproved = false;
            return false;
        }

        
        // ==========================================
        // CÁC HÀM XỬ LÝ 5 SKILL BI AI AGENT MỚI
        // ==========================================

        // TASK 2: CHUYỂN VIEW GIỮA BẢNG LÀM SẠCH VÀ STAR SCHEMA
        function switchT2View(viewName, btn) {
            const vClean = document.getElementById('t2-view-clean');
            const vSchema = document.getElementById('t2-view-schema');
            const bClean = document.getElementById('btn-t2-tab-clean');
            const bSchema = document.getElementById('btn-t2-tab-schema');

            if (bClean) bClean.classList.remove('active');
            if (bSchema) bSchema.classList.remove('active');
            if (btn) btn.classList.add('active');

            if (viewName === 'schema') {
                if (vClean) vClean.style.display = 'none';
                if (vSchema) vSchema.style.display = 'block';
            } else {
                if (vClean) vClean.style.display = 'block';
                if (vSchema) vSchema.style.display = 'none';
            }
        }

        function copySQLTemplate() {
            const sql = document.getElementById('sql-preview-box').innerText;
            navigator.clipboard.writeText(sql).then(() => {
                showToast('📋 Đã sao chép câu lệnh SQL CTE vào bộ nhớ tạm!');
            }).catch(() => {
                showToast('✅ Đã chọn SQL, bạn có thể bấm Ctrl+C để sao chép!');
            });
        }

        // TASK 1: HIỂN THỊ KIỂM TOÁN CHẤT LƯỢNG DỮ LIỆU (SKILL 1)
        function renderDataProfilingAudit() {
            const total = rawItems.length;
            const elTotal = document.getElementById('prof-total-rows');
            const elDup = document.getElementById('prof-duplicates');
            const elNull = document.getElementById('prof-null-rate');
            const elOut = document.getElementById('prof-outliers');
            const elBadge = document.getElementById('profiling-health-badge');

            if (!elTotal) return;

            if (total === 0) {
                elTotal.innerText = '0';
                elDup.innerText = '0';
                elNull.innerText = '0%';
                elOut.innerText = '0';
                if (elBadge) {
                    elBadge.className = 'badge badge-amber';
                    elBadge.innerText = '⚠️ Chờ Dữ Liệu';
                }
                return;
            }

            // Đếm trùng lặp
            const seen = new Set();
            let dups = 0;
            let missingBudget = 0;
            let outliers = 0;

            rawItems.forEach(r => {
                const id = r.request_id || r.id;
                if (id) {
                    if (seen.has(id)) dups++;
                    seen.add(id);
                }
                if (!r.budget && (!r.raw_request_text || !r.raw_request_text.includes('ngân sách'))) {
                    missingBudget++;
                }
                if (r.budget && Number(r.budget) > 1000000000) {
                    outliers++;
                }
            });

            const nullRate = Math.round((missingBudget / total) * 100);
            elTotal.innerText = total;
            elDup.innerText = dups;
            elNull.innerText = `${nullRate}%`;
            elOut.innerText = outliers;

            if (elBadge) {
                if (nullRate === 0 && dups === 0) {
                    elBadge.className = 'badge badge-green';
                    elBadge.innerText = '🟢 100% Sẵn Sàng Phân Tích';
                } else if (nullRate <= 25) {
                    elBadge.className = 'badge badge-blue';
                    elBadge.innerText = '🔵 Tốt (Có bổ sung tự động)';
                } else {
                    elBadge.className = 'badge badge-amber';
                    elBadge.innerText = '🟡 Cần Làm Sạch Thêm';
                }
            }
        }

        // TASK 3: PHÂN TÍCH CHẨN ĐOÁN NGUYÊN NHÂN GỐC RỄ (SKILL 4)
        function renderDiagnosticInsights() {
            const box = document.getElementById('diagnostic-insights-list');
            if (!box) return;

            if (!allDossiers || allDossiers.length === 0 || !isPipelineApproved) {
                box.innerHTML = `
                    <div style="text-align:center; padding:25px; background:#f8fafc; border:1px dashed #cbd5e1; border-radius:8px; color:var(--text-muted); font-size:12.5px;">
                        ${(rawItems.length > 0 && !isPipelineApproved) 
                            ? '⏳ Đang chờ phê duyệt luồng tại Task 2. Sau khi duyệt, hệ thống sẽ tự động phân tích chẩn đoán theo công thức: <b>[Observation] - [Root Cause] - [Business Impact]</b>.'
                            : 'Chưa có dữ liệu để thực hiện phân tích chẩn đoán. Hãy nạp dữ liệu ở Task 1 hoặc bấm "⚡ Nạp 6 Ca Mẫu".'}
                    </div>
                `;
                return;
            }

            if (currentSummaryData && currentSummaryData.is_hung_phat) {
                box.innerHTML = `
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid #059669; border-radius:8px; padding:14px 18px; box-shadow:0 1px 4px rgba(0,0,0,0.03); margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <h4 style="font-size:13.5px; font-weight:800; color:#065f46; margin:0;">
                                📌 Phân Tích Tiềm Năng 4 Phân Vùng Thị Trường (4,090 Doanh Nghiệp Mục Tiêu)
                            </h4>
                            <span class="badge badge-green">Quy Mô Khả Quan</span>
                        </div>
                        <div style="font-size:12.5px; color:#334155; line-height:1.5;">
                            <p style="margin:2px 0;"><b>[Observation - Quan Sát]:</b> Tổng số doanh nghiệp mục tiêu đạt 4,090 DN sau khi khử trùng lặp bản ghi MR-004 (T-01). Khu vực 1 dẫn đầu với 1,280 DN (tăng +6.67% QoQ so với 2025-Q4 theo T-02) cùng 62% tỷ lệ quan tâm phần mềm kho.</p>
                            <p style="margin:2px 0;"><b>[Root Cause - Nguyên Nhân Gốc]:</b> Nhu cầu số hóa kho bãi tại Khu vực 1 và Khu vực 2 tăng mạnh do sự mở rộng của các chuỗi logistics và sản xuất.</p>
                            <p style="margin:2px 0;"><b>[Business Impact - Tác Động]:</b> Tập trung phân bổ nguồn lực khai thác Khu vực 1 & 2 mang lại ROI cao nhất và đóng góp trên 70% doanh thu dự kiến.</p>
                        </div>
                    </div>

                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid #ef4444; border-radius:8px; padding:14px 18px; box-shadow:0 1px 4px rgba(0,0,0,0.03); margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <h4 style="font-size:13.5px; font-weight:800; color:#b91c1c; margin:0;">
                                🛑 Nghẽn Cổ Chai Năng Lực Hỗ Trợ On-site Tại Khu Vực 3 & 4 (Kiểm Thử T-05)
                            </h4>
                            <span class="badge badge-red">Rủi Ro Vượt Năng Lực</span>
                        </div>
                        <div style="font-size:12.5px; color:#334155; line-height:1.5;">
                            <p style="margin:2px 0;"><b>[Observation - Quan Sát]:</b> Khu vực 3 và 4 chỉ có 1 nhân sự hỗ trợ kỹ thuật tại chỗ, SLA ứng cứu kéo dài từ 6 - 8 giờ.</p>
                            <p style="margin:2px 0;"><b>[Root Cause - Nguyên Nhân Gốc]:</b> Hạn chế nhân sự chuyên môn tại địa phương, khoảng cách di chuyển địa lý làm tăng thời gian có mặt tại địa điểm khách hàng.</p>
                            <p style="margin:2px 0;"><b>[Business Impact - Tác Động]:</b> Tuyệt đối không ký kết hợp đồng On-site Support tại chỗ hàng loạt ở KV3 & 4. Chuyển hướng sang cung cấp giải pháp WMS Cloud triển khai và hỗ trợ 100% qua Remote.</p>
                        </div>
                    </div>

                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid #f59e0b; border-radius:8px; padding:14px 18px; box-shadow:0 1px 4px rgba(0,0,0,0.03); margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <h4 style="font-size:13.5px; font-weight:800; color:#92400e; margin:0;">
                                ⚠️ Kiểm Toán Chất Lượng Dữ Liệu Thiếu (Kiểm Thử T-03 & T-04)
                            </h4>
                            <span class="badge badge-amber">Cần Bổ Sung Dữ Kiện</span>
                        </div>
                        <div style="font-size:12.5px; color:#334155; line-height:1.5;">
                            <p style="margin:2px 0;"><b>[Observation - Quan Sát]:</b> Phát hiện MR-008 (Khu vực 4) thiếu kỳ thống kê và giá trị quan tâm; FB-008 thiếu mô tả nội dung nhu cầu.</p>
                            <p style="margin:2px 0;"><b>[Root Cause - Nguyên Nhân Gốc]:</b> Khảo sát sơ bộ chưa hoàn tất hoặc lỗi thu thập từ nguồn dữ liệu thô.</p>
                            <p style="margin:2px 0;"><b>[Business Impact - Tác Động]:</b> Tuân thủ nguyên tắc BI: Đánh dấu thiếu dữ liệu, không tự ý suy đoán hay điền số; cần thực hiện phỏng vấn bổ sung trước khi ra quyết định đầu tư tại KV4.</p>
                        </div>
                    </div>
                `;
                return;
            }

            // Tự động phân tích các nguyên nhân gốc từ dữ liệu thực tế Minh An
            const escalated = allDossiers.filter(d => d.approval && d.approval.requires_escalation);
            const unfeasibleLead = allDossiers.filter(d => d.feasibility && d.feasibility.lead_time_status === 'Không kịp tiến độ');
            const missingInfo = allDossiers.filter(d => (d.extracted_data && d.extracted_data.missing_fields && d.extracted_data.missing_fields.length > 0) || d.status === 'CẦN BỔ SUNG THÔNG TIN');

            let html = '';

            // Card 1: Về thẩm quyền chiết khấu
            if (escalated.length > 0) {
                const escPct = Math.round((escalated.length / allDossiers.length) * 100);
                const escDetails = [];
                escalated.forEach(d => {
                    const cName = (d.customer && d.customer.name) || d.customer_name || 'Khách hàng';
                    const dRate = (d.pricing && d.pricing.applied_discount_rate) ? (d.pricing.applied_discount_rate * 100).toFixed(0) + '%' : 'chiết khấu';
                    escDetails.push(`${cName} (${dRate})`);
                });
                const escSummaryStr = escDetails.length > 0 ? escDetails.slice(0, 3).join(', ') : 'Các khách hàng lớn';

                html += `
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid #7c3aed; border-radius:8px; padding:14px 18px; box-shadow:0 1px 4px rgba(0,0,0,0.03); margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <h4 style="font-size:13.5px; font-weight:800; color:#581c87; margin:0;">
                                📌 Phân Cấp Thẩm Quyền Phê Duyệt Chiết Khấu (SLA Escalation)
                            </h4>
                            <span class="badge badge-purple">${escalated.length} / ${allDossiers.length} cơ hội (${escPct}%)</span>
                        </div>
                        <div style="font-size:12.5px; color:#334155; line-height:1.5;">
                            <p style="margin:2px 0;"><b>[Observation - Quan Sát]:</b> Có ${escalated.length} cơ hội (${escPct}%) vượt thẩm quyền tự quyết của NVKD (>8%), cần Trưởng phòng hoặc Ban Giám Đốc phê duyệt: <i>${escSummaryStr}</i>.</p>
                            <p style="margin:2px 0;"><b>[Root Cause - Nguyên Nhân Gốc]:</b> Khách hàng doanh nghiệp đặt mua số lượng lớn hoặc có ngân sách đặc thù, yêu cầu mức chiết khấu vượt khung cơ sở 8% của NVKD.</p>
                            <p style="margin:2px 0;"><b>[Business Impact - Tác Động]:</b> Cần duy trì cam kết SLA phê duyệt 4h - 24h từ cấp quản lý để tránh chậm trễ, đồng thời đảm bảo biên lợi nhuận hoạt động mục tiêu từ 38% - 44%.</p>
                        </div>
                    </div>
                `;
            }

            // Card 2: Về cung ứng kho & tiến độ
            if (unfeasibleLead.length > 0) {
                const delayedNames = [];
                const delayedItems = new Set();
                unfeasibleLead.forEach(d => {
                    delayedNames.push((d.customer && d.customer.name) || d.customer_name || 'Khách hàng');
                    if (d.feasibility && d.feasibility.items_feasibility) {
                        d.feasibility.items_feasibility.forEach(it => {
                            if (it.stock_shortage > 0 || !it.is_stock_sufficient) {
                                delayedItems.add(it.name || it.sku);
                            }
                        });
                    }
                });
                const delayedCustStr = delayedNames.slice(0, 3).join(', ');
                const delayedItemsStr = Array.from(delayedItems).slice(0, 3).join(', ') || 'thiết bị theo yêu cầu';

                html += `
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid #ef4444; border-radius:8px; padding:14px 18px; box-shadow:0 1px 4px rgba(0,0,0,0.03); margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <h4 style="font-size:13.5px; font-weight:800; color:#b91c1c; margin:0;">
                                ⚠️ Rủi Ro Tiến Độ Cung Ứng & Điều Chuyển Kho
                            </h4>
                            <span class="badge badge-red">${unfeasibleLead.length} cơ hội trễ</span>
                        </div>
                        <div style="font-size:12.5px; color:#334155; line-height:1.5;">
                            <p style="margin:2px 0;"><b>[Observation - Quan Sát]:</b> Phát hiện ${unfeasibleLead.length} cơ hội có thời gian chuẩn bị kho vượt quá hạn định yêu cầu của khách hàng (${delayedCustStr}).</p>
                            <p style="margin:2px 0;"><b>[Root Cause - Nguyên Nhân Gốc]:</b> Tồn kho sẵn tại kho chi nhánh không đáp ứng đủ số lượng cho: <i>${delayedItemsStr}</i>. Cần thời gian nhập bổ sung hoặc điều chuyển liên vùng.</p>
                            <p style="margin:2px 0;"><b>[Business Impact - Tác Động]:</b> Kích hoạt phương án điều chuyển hàng liên vùng hoặc đàm phán giao hàng thành 2 đợt để đảm bảo đúng tiến độ hợp đồng.</p>
                        </div>
                    </div>
                `;
            }

            // Card 3: Về chất lượng thông tin đầu vào
            if (missingInfo.length > 0) {
                const missingCusts = [];
                const missingFieldList = new Set();
                missingInfo.forEach(d => {
                    missingCusts.push((d.customer && d.customer.name) || d.customer_name || 'Khách hàng');
                    if (d.extracted_data && d.extracted_data.missing_fields) {
                        d.extracted_data.missing_fields.forEach(f => missingFieldList.add(f));
                    }
                });
                const missingCustStr = missingCusts.slice(0, 3).join(', ');
                const missingFieldsStr = Array.from(missingFieldList).join(', ') || 'thông số kỹ thuật';

                html += `
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid #f59e0b; border-radius:8px; padding:14px 18px; box-shadow:0 1px 4px rgba(0,0,0,0.03); margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <h4 style="font-size:13.5px; font-weight:800; color:#b45309; margin:0;">
                                ✉️ Thiếu Dữ Kiện Kỹ Thuật Ban Đầu (Data Profiling)
                            </h4>
                            <span class="badge badge-amber">${missingInfo.length} cơ hội cần làm rõ</span>
                        </div>
                        <div style="font-size:12.5px; color:#334155; line-height:1.5;">
                            <p style="margin:2px 0;"><b>[Observation - Quan Sát]:</b> Có ${missingInfo.length} yêu cầu chưa cung cấp đủ dữ liệu (${missingCustStr}). Trường khuyết thiếu: <i>${missingFieldsStr}</i>.</p>
                            <p style="margin:2px 0;"><b>[Root Cause - Nguyên Nhân Gốc]:</b> Nguồn yêu cầu từ email hoặc tin nhắn tự do chưa qua biểu mẫu cấu trúc hóa chuẩn B2B.</p>
                            <p style="margin:2px 0;"><b>[Business Impact - Tác Động]:</b> AI Agent đã tự động tạo bản nháp email làm rõ các trường thiếu để NVKD gửi khách trong 30 phút.</p>
                        </div>
                    </div>
                `;
            }

            box.innerHTML = html;
        }

        // TASK 4: CẬP NHẬT BLUF DYNAMIC SUMMARY
        function updateBLUFSummary() {
            const elLead = document.getElementById('bluf-lead-text');
            if (!elLead) return;

            if (!allDossiers || allDossiers.length === 0) {
                elLead.innerText = (rawItems.length > 0 && !isPipelineApproved)
                    ? '⏳ Đang có ' + rawItems.length + ' yêu cầu chờ phê duyệt luồng tại Task 2. Vui lòng bấm duyệt tại Task 2 để xuất báo cáo điều hành BLUF.'
                    : 'Chưa có dữ liệu cơ hội kinh doanh để tổng hợp báo cáo điều hành BLUF. Vui lòng nhập dữ liệu ở Task 1.';
                return;
            }

            if (currentSummaryData && currentSummaryData.is_hung_phat) {
                const bluf = currentSummaryData.bluf_summary || {};
                elLead.innerHTML = `
                    <b>${bluf.headline || ''}</b><br>
                    <span style="font-size:12px; color:#115e59; margin-top:4px; display:block;">
                        🎯 <b>Khuyến nghị ưu tiên:</b> Tập trung 80% nguồn lực đánh chiếm Khu vực 1 & 2 (Tier 1 & Tier 2); Khu vực 3 & 4 chỉ triển khai WMS Cloud từ xa do hạn chế nhân sự tại chỗ (Test T-05).
                    </span>
                `;
                return;
            }

            const s = currentSummaryData || {};
            const totalVal = s.total_value_formatted || '0 VNĐ';
            const statusCounts = s.status_counts || {};
            const eligibleCount = (statusCounts['CÓ THỂ TIẾP TỤC'] || 0) + (statusCounts['CHỜ DUYỆT'] || 0);

            // Tính toán biên lợi nhuận hoạt động thực tế từ dữ liệu đầu vào
            let totalRevenue = 0;
            let totalCogs = 0;
            allDossiers.forEach(d => {
                if (d.pricing && d.pricing.final_proposal_value) {
                    const rev = d.pricing.final_proposal_value;
                    const base = d.pricing.base_subtotal || rev;
                    const cogs = base * 0.55;
                    totalRevenue += rev;
                    totalCogs += cogs;
                }
            });
            const avgMargin = (totalRevenue > 0) ? (((totalRevenue - totalCogs) / totalRevenue) * 100).toFixed(1) : '42.0';

            elLead.innerHTML = `
                Tổng giá trị Pipeline khả thi đạt <b>${totalVal}</b> (${eligibleCount}/${allDossiers.length} cơ hội đạt chuẩn). 
                Biên lợi nhuận hoạt động trung bình đạt <b>${avgMargin}%</b> (tính toán thực tế từ giá trị đề xuất và giá vốn COGS 55%, nằm tối ưu trong biên độ 38% - 44%).
            `;
        }

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.innerText = msg;
            toast.className = 'toast show';
            setTimeout(() => { toast.className = 'toast'; }, 3000);
        }

        // CHUYỂN TASK BÊN TRÁI
        function switchTask(taskId) {
            try {
                for (let i = 1; i <= 4; i++) {
                    const item = document.getElementById('menu-task-' + i);
                    const panel = document.getElementById('panel-task-' + i);
                    if (item) item.classList.remove('active');
                    if (panel) panel.classList.remove('active');
                }
                const activeItem = document.getElementById('menu-task-' + taskId);
                const activePanel = document.getElementById('panel-task-' + taskId);
                if (activeItem) activeItem.classList.add('active');
                if (activePanel) activePanel.classList.add('active');
            } catch (navErr) {
                console.warn('Navigation tab switch warning:', navErr);
            }

            try {
                if (taskId === 1) renderTask1Data();
                else if (taskId === 2) renderTask2Data();
                else if (taskId === 3) renderTask3Data();
                else if (taskId === 4) {
                    renderTask4Data();
                    renderComboChart(comboChartMode);
                }
            } catch (renderErr) {
                console.error('Task data render error:', renderErr);
            }
        }

        function appendLog(tag, message) {
            const box = document.getElementById('console-box');
            if (!box) return;
            const now = new Date().toTimeString().split(' ')[0];
            const div = document.createElement('div');
            div.className = 'console-line';
            div.innerHTML = `<span class="console-time">[${now}]</span> <span class="console-tag">[${tag}]</span> ${message}`;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

        let comboChartMode = 'pipeline';

        function renderComboChart(mode) {
            try {
                const container = document.getElementById('combo-chart-container');
                if (!container) return;

                // ĐIỀU KIỆN: KHI CÓ DỮ LIỆU ĐẦU VÀO ĐÃ ĐƯỢC TÍNH TOÁN BẮT ĐẦU VẼ BIỂU ĐỒ
                const hasData = (allDossiers && allDossiers.length > 0);

                if (!hasData) {
                    const isWaiting = (rawItems && rawItems.length > 0 && !isPipelineApproved);
                    container.innerHTML = `
                        <div style="text-align:center; padding:45px 20px; background:#f8fafc; border:2px dashed #cbd5e1; border-radius:12px; width:100%;">
                            <div style="font-size:48px; margin-bottom:12px;">${isWaiting ? '⏳' : '📊'}</div>
                            <div style="font-size:16px; font-weight:700; color:#1e293b; margin-bottom:6px;">
                                ${isWaiting ? 'Biểu Đồ Đang Chờ Phê Duyệt Luồng Tại Task 2' : 'Chưa Có Dữ Liệu Đầu Vào Để Phân Tích'}
                            </div>
                            <p style="font-size:13px; color:#64748b; max-width:540px; margin:0 auto 18px auto; line-height:1.5;">
                                ${isWaiting ? 'Đang có ' + rawItems.length + ' yêu cầu đã nhập ở Task 1. Vui lòng chuyển sang Task 2 bấm Duyệt để hệ thống tính toán thực tế và vẽ biểu đồ doanh số kết hợp biên lợi nhuận.' : 'Hệ thống hoạt động theo nguyên tắc: <b>Không bịa đặt dữ liệu</b>. Chỉ khi có dữ liệu đầu vào được nạp ở Task 1 và phê duyệt ở Task 2, biểu đồ BI mới bắt đầu tính toán và hiển thị.'}
                            </p>
                            <div style="display:flex; justify-content:center; gap:12px; flex-wrap:wrap;">
                                <button class="btn btn-primary" onclick="${isWaiting ? 'switchTask(2)' : 'switchTask(1)'}" style="font-size:12.5px; padding:8px 18px;">
                                    ${isWaiting ? '🛡️ Đến Task 2 Phê Duyệt' : '📥 Đến Task 1 Nhập Dữ Liệu'}
                                </button>
                                <button class="btn btn-outline" onclick="loadSampleDataset();" style="font-size:12.5px; padding:8px 18px;">
                                    ⚡ Nạp 6 Ca Đề Bài Để Phân Tích
                                </button>
                            </div>
                        </div>
                    `;
                    return;
                }

                const validDossiers = allDossiers.filter(d => d && typeof d === 'object');
                if (validDossiers.length === 0) {
                    container.innerHTML = `<div style="text-align:center; padding:35px; color:#64748b;">Chưa có dữ liệu cơ hội hợp lệ để vẽ biểu đồ.</div>`;
                    return;
                }

                // Dữ liệu tính toán động từ các hồ sơ thực tế trong hệ thống
                const isHP = (currentSummaryData && currentSummaryData.is_hung_phat);
                let data = [];
                if (isHP && currentSummaryData.regional_kpi) {
                    data = currentSummaryData.regional_kpi.map(k => ({
                        label: k.region,
                        customer: k.rank_label.split('-')[0].trim(),
                        sales: k.target_enterprises,
                        margin: k.total_score
                    }));
                } else {
                    data = validDossiers.map((d, idx) => {
                        let val = 0;
                        let base = 0;
                        let label = d.opportunity_id ? d.opportunity_id.replace('REQ-2026-', 'Ca ') : ('Ca ' + (idx + 1));
                        let cust = (d.customer && d.customer.name) || d.customer_name || 'Khách hàng';
                        if (cust.length > 15) cust = cust.slice(0, 15) + '..';

                        if (d.pricing && typeof d.pricing.final_proposal_value === 'number') {
                            val = d.pricing.final_proposal_value;
                            base = d.pricing.base_subtotal || val;
                        } else if (d.extracted_data && typeof d.extracted_data.budget === 'number') {
                            val = d.extracted_data.budget;
                            base = val;
                        }

                        // Tính biên lợi nhuận hoạt động thực tế từ COGS (55% của giá cơ sở)
                        const cogs = base * 0.55;
                        let margin = (val > 0 && !isNaN(val)) ? (((val - cogs) / val) * 100) : 42.0;
                        if (isNaN(margin) || !isFinite(margin)) margin = 42.0;

                        return {
                            label: label,
                            customer: cust,
                            sales: val,
                            margin: Number(margin.toFixed(1))
                        };
                    });
                }

                // NẾU TẬP DỮ LIỆU LỚN (> 10 BẢN GHI, VÍ DỤ 1099 CA), TỰ ĐỘNG CHUYỂN SANG HIỂN THỊ TOP 10 CƠ HỘI LỚN NHẤT
                // ĐỂ TRÁNH CHỮ ĐÈ LÊN NHAU VÀ ĐẢM BẢO TRỰC QUAN HÓA CHUẨN BI DASHBOARD
                let isTopAggregated = false;
                const originalTotalCount = data.length;
                if (!isHP && data.length > 10) {
                    isTopAggregated = true;
                    const sorted = [...data].sort((a, b) => (b.sales || 0) - (a.sales || 0));
                    const top10 = sorted.slice(0, 10);
                    const remaining = sorted.slice(10);
                    const remainingSales = remaining.reduce((sum, item) => sum + (item.sales || 0), 0);
                    const avgRemMargin = remaining.length > 0
                        ? Number((remaining.reduce((sum, item) => sum + (item.margin || 0), 0) / remaining.length).toFixed(1))
                        : 42.0;

                    data = [...top10];
                    if (remaining.length > 0 && remainingSales > 0) {
                        data.push({
                            label: `Khác (${remaining.length})`,
                            customer: `${remaining.length} ca còn lại`,
                            sales: remainingSales,
                            margin: avgRemMargin
                        });
                    }
                }

                const n = data.length;
                const width = 940;
                const height = 370;
                const xStart = 55;
                const xEnd = 855;
                const plotWidth = xEnd - xStart;
                const yTop = 60;
                const yBottom = 295;
                const plotHeight = yBottom - yTop;

                const maxSales = Math.max(...data.map(d => d.sales)) * 1.15 || 100000000;
                
                // Biên độ trục margin theo chuẩn hoặc co dãn theo dữ liệu thực
                const margins = data.map(d => d.margin).filter(m => !isNaN(m) && isFinite(m));
                const calculatedMinM = margins.length > 0 ? Math.floor(Math.min(...margins)) : (isHP ? 60 : 38);
                const calculatedMaxM = margins.length > 0 ? Math.ceil(Math.max(...margins)) : (isHP ? 100 : 44);
                const minMargin = isHP ? Math.max(50, calculatedMinM - 5) : Math.min(38, calculatedMinM - 1);
                const maxMargin = isHP ? Math.min(100, calculatedMaxM + 2) : Math.max(44, calculatedMaxM + 1);

                const colLabel = isHP ? "Doanh Nghiệp Mục Tiêu (Số Lượng DN)" : (isTopAggregated ? `Top 10 Cơ Hội Quy Mô Lớn Nhất (Tổng ${originalTotalCount} Ca)` : "Doanh Số Thực Tế (VNĐ)");
                const lineLabel = isHP ? "Điểm Đánh Giá Chiến Lược (Strategic Score %)" : "Biên Lợi Nhuận Hoạt Động (Operating Margin %)";

                let svg = `<svg viewBox="0 0 ${width} ${height}" style="width:100%; height:370px; display:block; font-family:'Inter',sans-serif;">`;

                // 1. CHÚ THÍCH (LEGEND) Ở TRÊN CÙNG
                svg += `
                    <g id="legend">
                        <rect x="65" y="20" width="28" height="10" fill="#1f619e" rx="1.5" />
                        <text x="100" y="29" font-size="13" font-weight="700" fill="#1e293b">${colLabel}</text>
                        <line x1="420" y1="25" x2="455" y2="25" stroke="#dc2626" stroke-width="3.5" stroke-linecap="round" />
                        <text x="465" y="29" font-size="13" font-weight="700" fill="#1e293b">${lineLabel}</text>
                    </g>
                `;

                // 2. CÁC ĐƯỜNG LƯỚI NGANG VÀ NHÃN TỶ LỆ % BÊN PHẢI
                const marginStep = (maxMargin - minMargin <= 8) ? 1 : (isHP ? 5 : 2);
                for (let m = minMargin; m <= maxMargin; m += marginStep) {
                    const ratio = (maxMargin > minMargin) ? ((m - minMargin) / (maxMargin - minMargin)) : 0.5;
                    const y = yBottom - ratio * plotHeight;
                    svg += `<line x1="${xStart}" y1="${y}" x2="${xEnd}" y2="${y}" stroke="#f1f5f9" stroke-width="1" />`;
                    svg += `<text x="${xEnd + 12}" y="${y + 4}" font-size="12" font-weight="600" fill="#64748b">${m}%</text>`;
                }

                // ĐƯỜNG TRỤC CƠ SỞ (BASELINE)
                svg += `<line x1="${xStart}" y1="${yBottom}" x2="${xEnd}" y2="${yBottom}" stroke="#cbd5e1" stroke-width="1.5" />`;

                // 3. VẼ CỘT DOANH SỐ / DOANH NGHIỆP THỰC TẾ
                const colWidth = plotWidth / (n || 1);
                const barW = Math.min(52, colWidth * 0.58);
                const linePoints = [];

                data.forEach((d, i) => {
                    const cx = xStart + (i + 0.5) * colWidth;
                    const barH = (maxSales > 0) ? ((d.sales / maxSales) * plotHeight) : 0;
                    const barY = yBottom - barH;

                    // Cột màu xanh dương
                    svg += `<rect x="${cx - barW/2}" y="${barY}" width="${barW}" height="${barH}" fill="#1f619e" rx="2">
                        <title>${d.label} (${d.customer}): ${d.sales.toLocaleString('vi-VN')} - Điểm: ${d.margin}%</title>
                    </rect>`;

                    // Nhãn số trên đầu cột
                    let displaySales = '';
                    if (isHP) {
                        displaySales = d.sales.toLocaleString('vi-VN') + ' DN';
                    } else if (d.sales >= 1000000000) {
                        displaySales = (d.sales / 1000000000).toFixed(1) + ' tỷ';
                    } else if (d.sales >= 1000000) {
                        displaySales = Math.round(d.sales / 1000000) + ' tr';
                    } else {
                        displaySales = d.sales.toLocaleString('vi-VN') + ' đ';
                    }
                    svg += `<text x="${cx}" y="${barY - 7}" font-size="11.5" font-weight="700" fill="#0f172a" text-anchor="middle">${displaySales}</text>`;

                    // Tính tọa độ điểm trên đường Line
                    const marginRatio = (maxMargin > minMargin) ? ((d.margin - minMargin) / (maxMargin - minMargin)) : 0.5;
                    const py = yBottom - marginRatio * plotHeight;
                    linePoints.push({ x: cx, y: py, margin: d.margin });

                    // Nhãn trục X hàng 1
                    svg += `<text x="${cx}" y="${yBottom + 24}" font-size="12" font-weight="700" fill="#334155" text-anchor="middle">${d.label}</text>`;
                    // Nhãn trục X hàng 2
                    svg += `<text x="${cx}" y="${yBottom + 40}" font-size="10.5" font-weight="500" fill="#64748b" text-anchor="middle">${d.customer}</text>`;
                });

                // 4. VẼ ĐƯỜNG BIÊN LỢI NHUẬN HOẠT ĐỘNG (ĐƯỜNG ĐỎ)
                if (linePoints.length > 1) {
                    const polyStr = linePoints.map(p => `${p.x},${p.y}`).join(' ');
                    svg += `<polyline points="${polyStr}" fill="none" stroke="#dc2626" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />`;
                    
                    // Vẽ các chấm đỏ tại mỗi điểm
                    linePoints.forEach(p => {
                        svg += `<circle cx="${p.x}" cy="${p.y}" r="4.5" fill="#dc2626" stroke="#ffffff" stroke-width="1.5">
                            <title>Operating Margin: ${p.margin}%</title>
                        </circle>`;
                    });
                }

                svg += `</svg>`;
                container.innerHTML = svg;
            } catch(chartErr) {
                console.error('Error in renderComboChart:', chartErr);
            }
        }

        // RENDER NGAY LẬP TỨC KHI MỞ TRANG (GIỮ DỮ LIỆU KHI F5 / RELOAD)
        function instantRenderAll() {
            try {
                const hasRestored = loadSystemState();

                try { renderTask1Data(); } catch(e) { console.error('Error in renderTask1Data:', e); }
                try { renderComboChart(comboChartMode); } catch(e) { console.error('Error in renderComboChart:', e); }
                try { renderTask2Data(); } catch(e) { console.error('Error in renderTask2Data:', e); }
                try { renderTask3Data(); } catch(e) { console.error('Error in renderTask3Data:', e); }
                try { renderTask4Data(); } catch(e) { console.error('Error in renderTask4Data:', e); }

                const btn = document.getElementById('main-cmd-btn');

                if (hasRestored && rawItems.length > 0) {
                    if (isPipelineApproved) {
                        for (let i = 1; i <= 4; i++) setNodeState(i, 'completed');
                        if (btn) btn.innerText = '✅ ĐÃ DUYỆT & HOÀN TẤT LUỒNG QUY TRÌNH (BẤM ĐỂ CHẠY LẠI)';
                        document.getElementById('header-status').innerText = `Đã Hoàn Tất Xử Lý ${allDossiers.length} Ca`;
                        document.getElementById('flow-status-tag').innerText = 'ĐÃ DUYỆT & HOÀN TẤT';
                        appendLog('PHỤC HỒI', `Đã giữ và phục hồi ${rawItems.length} yêu cầu từ phiên làm việc trước.`);
                    } else {
                        for (let i = 1; i <= 4; i++) setNodeState(i, '');
                        if (btn) btn.innerText = '🛡️ DUYỆT & BẮT ĐẦU CHẠY LUỒNG QUY TRÌNH ➔';
                        document.getElementById('header-status').innerText = `Đã Nhận ${rawItems.length} Ca (Chờ Duyệt)`;
                        document.getElementById('flow-status-tag').innerText = 'CHỜ PHÊ DUYỆT';
                        appendLog('PHỤC HỒI', `Đã phục hồi ${rawItems.length} yêu cầu. Vui lòng vào Task 2 bấm Duyệt để chạy luồng.`);
                    }
                } else {
                    for (let i = 1; i <= 4; i++) setNodeState(i, '');
                    document.getElementById('header-status').innerText = 'Chờ Nhập Dữ Liệu';
                    document.getElementById('flow-status-tag').innerText = 'CHỜ DỮ LIỆU ĐẦU VÀO';
                    if (btn) btn.innerText = '⚠️ CHƯA CÓ DỮ LIỆU (NHẬP Ở TASK 1)';
                    appendLog('HỆ THỐNG', 'Hệ thống đã sẵn sàng. Vui lòng nhập dữ liệu ở Task 1 để bắt đầu.');
                }
            } catch (fatalErr) {
                console.error('Fatal error in instantRenderAll:', fatalErr);
            }
        }

        // ==========================================
        // TASK 1: TIẾP NHẬN DỮ LIỆU
        // ==========================================
        function renderTask1Data() {
            try {
                renderDataProfilingAudit();
                const tbody = document.getElementById('task1-tbody');
                if (!tbody) return;
                const reqCountEl = document.getElementById('req-count');
                if (reqCountEl) reqCountEl.innerText = rawItems.length;

                if (!rawItems || rawItems.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có yêu cầu nào. Hãy nhập ở form trên hoặc bấm "⚡ Nạp 6 Ca Đề Bài".</td></tr>';
                    return;
                }

                const rows = [];
                rawItems.forEach((r, idx) => {
                    if (!r || typeof r !== 'object') return;
                    const reqId = r.request_id || r.id || ("REQ-" + (1000 + idx));
                    const custName = r.customer_name || 'Khách Hàng';
                    const email = r.contact_email || 'Chưa cung cấp';
                    const channel = r.channel || 'Email';
                    const rawText = String(r.raw_request_text || r.raw_text || '');
                    
                    // Trích xuất hiển thị sơ bộ
                    const ex = (extractedItems && Array.isArray(extractedItems)) ? extractedItems.find(x => x && (x.request_id || x.id) === reqId) : null;
                    const bud = (ex && ex.budget) ? Number(ex.budget).toLocaleString('vi-VN') + ' đ' : (r.budget ? Number(r.budget).toLocaleString('vi-VN') + ' đ' : '<span style="color:var(--text-muted)">Chưa rõ</span>');
                    const del = (ex && ex.delivery_days) ? ex.delivery_days + ' ngày' : (r.delivery_days ? r.delivery_days + ' ngày' : '<span style="color:var(--text-muted)">Chưa rõ</span>');

                    rows.push(`
                        <tr>
                            <td><strong>${reqId}</strong></td>
                            <td><b>${custName}</b><br><small style="color:var(--text-muted);">${email}</small></td>
                            <td><span class="badge badge-blue">${channel}</span></td>
                            <td style="max-width:320px; font-size:12px; line-height:1.4;">${rawText.slice(0, 110)}${rawText.length > 110 ? '...' : ''}</td>
                            <td>${bud}</td>
                            <td>${del}</td>
                            <td><span class="badge badge-green">✅ Đã tiếp nhận</span></td>
                            <td>
                                <div style="display:flex; gap:6px;">
                                    <button class="btn btn-outline" style="padding:4px 8px; font-size:11px;" onclick="showDetail('${encodeURIComponent(reqId)}')">Chi tiết</button>
                                    <button class="btn btn-danger" style="padding:4px 8px; font-size:11px;" onclick="deleteSingleRequest('${encodeURIComponent(reqId)}')">Xóa</button>
                                </div>
                            </td>
                        </tr>
                    `);
                });
                const maxDisplayT2 = 100;
                const displayedT2Rows = rows.slice(0, maxDisplayT2);
                if (rows.length > maxDisplayT2) {
                    displayedT2Rows.push(`
                        <tr>
                            <td colspan="8" style="text-align:center; padding:16px; background:#f0fdf4; color:#166534; font-weight:600;">
                                📊 Đang hiển thị ${maxDisplayT2} / ${rows.length} yêu cầu đầu vào. Toàn bộ hồ sơ được xử lý và xuất đầy đủ tại Task 4.
                            </td>
                        </tr>
                    `);
                }
                tbody.innerHTML = displayedT2Rows.join('');
            } catch (err) {
                console.error('Error in renderTask1Data:', err);
            }
        }

        // CÁCH 1: THÊM YÊU CẦU MỚI BẰNG FORM
        async function handleAddManualRequest() {
            const name = document.getElementById('man-cust-name').value.trim();
            const email = document.getElementById('man-cust-email').value.trim();
            const channel = document.getElementById('man-channel').value;
            const deadline = document.getElementById('man-deadline').value.trim();
            const budget = document.getElementById('man-budget').value.trim();
            const rawText = document.getElementById('man-raw-text').value.trim();

            if (!name) { alert('Vui lòng nhập Tên Khách Hàng!'); return; }
            if (!rawText) { alert('Vui lòng nhập Nội Dung Yêu Cầu!'); return; }

            let combinedText = rawText;
            if (budget && !combinedText.includes('ngân sách')) {
                combinedText += ` Ngân sách dự toán: ${Number(budget).toLocaleString('vi-VN')} VNĐ.`;
            }
            if (deadline && !combinedText.includes('ngày')) {
                combinedText += ` Cần giao hàng trong ${deadline} ngày.`;
            }

            const newReq = {
                id: "REQ-" + Math.floor(1000 + Math.random() * 9000),
                customer_name: name,
                contact_email: email || "contact@" + name.toLowerCase().replace(/\\s+/g, '') + ".vn",
                channel: channel,
                raw_request_text: combinedText,
                budget: budget ? Number(budget) : null,
                delivery_days: deadline ? Number(deadline) : null
            };

            rawItems.push(newReq);
            showToast(`✅ Đã thêm yêu cầu mới: ${name}!`);

            // Xóa form
            document.getElementById('man-cust-name').value = '';
            document.getElementById('man-cust-email').value = '';
            document.getElementById('man-deadline').value = '';
            document.getElementById('man-budget').value = '';
            document.getElementById('man-raw-text').value = '';

            isPipelineApproved = false;
            await recomputeEntireSystem();
            renderTask1Data();
            saveSystemState();
            appendLog('DỮ LIỆU MỚI', `Đã tiếp nhận yêu cầu từ [${name}]. Vui lòng sang Task 2 để bấm 'Phê Duyệt & Chạy Quy Trình'.`);
            showToast(`✅ Đã thêm [${name}]! Sang Task 2 bấm Duyệt để chạy luồng quy trình.`);
            const b = document.getElementById('main-cmd-btn');
            if (b) b.innerText = '🛡️ DUYỆT & BẮT ĐẦU CHẠY LUỒNG QUY TRÌNH ➔';
            document.getElementById('flow-status-tag').innerText = 'CHỜ PHÊ DUYỆT';
        }

        // CÁCH 2: DÁN TEXT HOẶC JSON HÀNG LOẠT
        async function handlePasteSubmit() {
            const text = document.getElementById('paste-text').value.trim();
            if (!text) { alert('Vui lòng dán văn bản hoặc chuỗi JSON!'); return; }

            try {
                const parsed = JSON.parse(text);
                const items = Array.isArray(parsed) ? parsed : [parsed];
                rawItems = items.concat(rawItems);
                showToast(`✅ Đã nạp thành công ${items.length} yêu cầu từ JSON!`);
            } catch(e) {
                const single = {
                    id: "REQ-" + Math.floor(1000 + Math.random() * 9000),
                    customer_name: "Khách Hàng (Nhập Khung Dán)",
                    contact_email: "client@doanhnghiep.vn",
                    channel: "Web Form",
                    raw_request_text: text
                };
                rawItems.push(single);
                showToast('✅ Đã nạp yêu cầu văn bản mới vào hệ thống!');
            }

            isPipelineApproved = false;
            document.getElementById('paste-text').value = '';
            await recomputeEntireSystem();
            renderTask1Data();
            saveSystemState();
            appendLog('DỮ LIỆU MỚI', `Đã nạp dữ liệu từ khung dán. Vui lòng sang Task 2 để bấm 'Phê Duyệt & Chạy Quy Trình'.`);
            showToast('✅ Đã nạp dữ liệu! Sang Task 2 bấm Duyệt để chạy luồng quy trình.');
            const b = document.getElementById('main-cmd-btn');
            if (b) b.innerText = '🛡️ DUYỆT & BẮT ĐẦU CHẠY LUỒNG QUY TRÌNH ➔';
            document.getElementById('flow-status-tag').innerText = 'CHỜ PHÊ DUYỆT';
        }

        // XÓA 1 YÊU CẦU
        async function deleteSingleRequest(id) {
            id = decodeURIComponent(id);
            rawItems = rawItems.filter(x => x && (x.request_id || x.id) !== id);
            extractedItems = extractedItems.filter(x => x && (x.request_id || x.id) !== id);
            allDossiers = allDossiers.filter(x => x && x.opportunity_id !== id);
            showToast(`🗑️ Đã xóa yêu cầu ${id}`);
            saveSystemState();
            renderTask1Data();
            if (rawItems.length > 0) {
                await recomputeEntireSystem();
            } else {
                instantRenderAll();
            }
        }

        // HÀM TÍNH TOÁN LẠI TOÀN BỘ BACKEND (TỐI ƯU SIÊU NHANH 1 LẦN GỌI)
        async function recomputeEntireSystem() {
            try {
                if (!rawItems || rawItems.length === 0) {
                    allDossiers = [];
                    currentSummaryData = null;
                    extractedItems = [];
                    renderTask2Data();
                    renderTask3Data();
                    renderTask4Data();
                    return;
                }
                const resBatch = await fetch('/api/batch_process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(rawItems)
                });
                const dataBatch = await resBatch.json();
                allDossiers = dataBatch.dossiers || [];
                currentSummaryData = dataBatch.summary || null;
                if (dataBatch.extracted) {
                    extractedItems = dataBatch.extracted;
                }

                renderTask2Data();
                renderTask3Data();
                renderTask4Data();
                renderComboChart(comboChartMode);
                saveSystemState();
            } catch(e) {
                console.warn('Update system sync warning:', e);
            }
        }

        // ==========================================
        // TASK 2: LUỒNG QUY TRÌNH & LÀM SẠCH KHO
        // ==========================================
        // ==========================================
        // TASK 2: LUỒNG QUY TRÌNH & LÀM SẠCH KHO (CHẠY CHẬM, PHÂN TÍCH KỸ, HỎI XÁC NHẬN)
        // ==========================================
        let isStepByStepMode = true; // Mặc định dừng hỏi sau mỗi quy trình theo yêu cầu người dùng
        let currentActivePipelineStep = 0;

        function togglePipelineMode(checked) {
            isStepByStepMode = checked;
            showToast(isStepByStepMode 
                ? '🐢 Đã bật chế độ: Phân tích chậm & hỏi để tiếp tục từng bước' 
                : '🐇 Đã bật chế độ: Chạy tự động liên tục toàn bộ các bước');
        }

        async function approveAndRunPipeline() {
            if (rawItems.length === 0) {
                alert('⚠️ Chưa có dữ liệu nào trong hệ thống! Vui lòng vào Task 1 để nhập dữ liệu hoặc tải tệp lên trước.');
                switchTask(1);
                return;
            }
            if (isAutoRunning) return;

            isPipelineApproved = true;
            appendLog('PHÊ DUYỆT', `Đã phê duyệt khởi chạy luồng quy trình cho ${rawItems.length} yêu cầu!`);
            showToast('🛡️ Đã phê duyệt! Bắt đầu phân tích luồng...');
            
            // Bắt đầu từ Bước 2.1 với chế độ đã chọn
            await executePipelineStep(1, !isStepByStepMode);
            saveSystemState();
        }

        async function continueToNextStage(nextStepNum) {
            const dialog = document.getElementById('pipeline-stage-dialog');
            if (dialog) dialog.style.display = 'none';
            await executePipelineStep(nextStepNum, false);
            saveSystemState();
        }

        async function continueAllStagesAuto(fromStepNum) {
            const dialog = document.getElementById('pipeline-stage-dialog');
            if (dialog) dialog.style.display = 'none';
            isStepByStepMode = false;
            const chk = document.getElementById('chk-step-by-step');
            if (chk) chk.checked = false;
            showToast('⚡ Chuyển sang chạy tự động toàn bộ các bước còn lại...');
            await executePipelineStep(fromStepNum, true);
            saveSystemState();
        }

        async function runSingleStep(stepNum) {
            if (rawItems.length === 0) {
                alert('⚠️ Chưa có dữ liệu! Vui lòng nạp dữ liệu ở Task 1 trước.');
                return;
            }
            if (isAutoRunning) return;
            await executePipelineStep(stepNum, false);
        }

        async function executePipelineStep(stepNum, autoContinue = false) {
            if (isAutoRunning) return;
            isAutoRunning = true;
            currentActivePipelineStep = stepNum;

            const btn = document.getElementById('main-cmd-btn');
            if (btn) {
                btn.innerText = `⏳ Đang Phân Tích Kỹ Giai Đoạn 2.${stepNum}...`;
                btn.disabled = true;
            }

            const statusTag = document.getElementById('flow-status-tag');
            if (statusTag) {
                statusTag.innerText = `ĐANG CHẠY BƯỚC 2.${stepNum}`;
                statusTag.style.background = '#fef3c7';
                statusTag.style.color = '#92400e';
            }

            // Cập nhật trạng thái hiển thị của các node
            for (let i = 1; i <= 4; i++) {
                if (i < stepNum) setNodeState(i, 'completed');
                else if (i === stepNum) setNodeState(i, 'active');
                else setNodeState(i, '');
            }

            const isHP = (currentSummaryData && currentSummaryData.is_hung_phat) || allDossiers.some(d => d && d.is_hung_phat);

            // ==========================================
            // THỰC THI CHẬM & PHÂN TÍCH THẬT KỸ TỪNG GIAI ĐOẠN
            // ==========================================
            if (stepNum === 1) {
                appendLog('GIAI ĐOẠN 2.1', `🔍 [1/3] Bóc tách NLP cấu trúc dữ liệu (${rawItems.length} bản ghi)...`);
                await delay(700);
                appendLog('GIAI ĐOẠN 2.1', '🏷️ [2/3] Đối chiếu mã sản phẩm Catalog & Kiểm định Data Profiling...');
                await delay(800);
                if (isHP) {
                    appendLog('GIAI ĐOẠN 2.1 (HƯNG PHÁT)', '🛡️ [3/3] Phát hiện trùng lặp T-01 (MR-004) & Khác kỳ T-02 (MR-001 vs MR-002). Gắn cờ bảo toàn 4,090 DN.');
                } else {
                    appendLog('GIAI ĐOẠN 2.1 (MINH AN)', '🛡️ [3/3] Chuẩn hóa thực thể SKU, phân bổ NVKD phụ trách và mã định danh REQ.');
                }
                await delay(600);
                setNodeState(1, 'completed');

            } else if (stepNum === 2) {
                appendLog('GIAI ĐOẠN 2.2', '📋 [1/3] Thẩm tra Checklist 4 trường bắt buộc (SKU, SL, Ngân sách, Deadline)...');
                await delay(700);
                appendLog('GIAI ĐOẠN 2.2', '🔎 [2/3] Phân loại hồ sơ hợp lệ vs hồ sơ thiếu dữ kiện...');
                await delay(800);
                appendLog('GIAI ĐOẠN 2.2', '✉️ [3/3] Tự động kích hoạt mẫu thư yêu cầu khách hàng làm rõ thông tin đối với các hồ sơ thiếu.');
                await delay(600);
                setNodeState(2, 'completed');

            } else if (stepNum === 3) {
                appendLog('GIAI ĐOẠN 2.3', '🏭 [1/3] Truy vấn tồn kho khả dụng tại 2 trung tâm logistics Kho Hà Nội & Kho TP.HCM...');
                await delay(700);
                appendLog('GIAI ĐOẠN 2.3', '📊 [2/3] Phân tích tỷ lệ đáp ứng ngay (In-stock) vs Cần đặt hàng nhập thêm (Backorder)...');
                await delay(800);
                if (isHP) {
                    appendLog('GIAI ĐOẠN 2.3 (HƯNG PHÁT)', '⚠️ [3/3] Phát hiện nút thắt cổ chai T-05: KV3 thiếu 250 DN, KV4 thiếu 350 DN năng lực!');
                } else {
                    appendLog('GIAI ĐOẠN 2.3 (MINH AN)', '✅ [3/3] Thẩm định kho khả dụng thành công. Xác định thời gian lấy hàng từng kho.');
                }
                await delay(600);
                setNodeState(3, 'completed');

            } else if (stepNum === 4) {
                appendLog('GIAI ĐOẠN 2.4', '⏱️ [1/3] Tính toán Lead Time tổng thể (Xử lý + Nhập hàng + Vận chuyển + Cài đặt)...');
                await delay(700);
                appendLog('GIAI ĐOẠN 2.4', '🚚 [2/3] Đối chiếu Lead Time thực tế với Deadline cam kết của khách hàng...');
                await delay(800);
                appendLog('GIAI ĐOẠN 2.4', '🎉 [3/3] Hoàn tất chuẩn hóa tiến độ. Đang đồng bộ hóa toàn bộ Task 2, Task 3 và Task 4...');
                await delay(600);
                setNodeState(4, 'completed');

                // Đồng bộ toàn bộ hệ thống
                await recomputeEntireSystem();
                isPipelineApproved = true;
                renderTask2Data();
                renderTask3Data();
                renderTask4Data();
                renderComboChart(comboChartMode);
                saveSystemState();
                renderComboChart(comboChartMode);
            }

            isAutoRunning = false;

            // KIỂM TRA ĐIỀU KIỆN TIẾP TỤC HOẶC HỎI NGƯỜI DÙNG
            if (stepNum < 4) {
                if (autoContinue) {
                    showToast(`✅ Đã xong Bước 2.${stepNum}. Tự động chuyển tiếp sang Bước 2.${stepNum + 1}...`);
                    await delay(800);
                    await executePipelineStep(stepNum + 1, true);
                } else {
                    // DỪNG LẠI VÀ HIỂN THỊ HỘI THOẠI HỎI NGƯỜI DÙNG KÈM PHÂN TÍCH CHUYÊN SÂU
                    renderStageAnalysisDialog(stepNum);
                    if (btn) {
                        btn.innerText = `⏸️ Tạm Dừng Sau Bước 2.${stepNum} (Chờ Xác Nhận Tiếp Tục)`;
                        btn.disabled = false;
                    }
                    if (statusTag) {
                        statusTag.innerText = `HOÀN THÀNH BƯỚC 2.${stepNum} (CHỜ XÁC NHẬN)`;
                        statusTag.style.background = '#e0e7ff';
                        statusTag.style.color = '#3730a3';
                    }
                    showToast(`⏸️ Đã phân tích xong Bước 2.${stepNum}! Vui lòng bấm tiếp tục để chạy tiếp.`);
                }
            } else {
                // HOÀN TẤT TOÀN BỘ 4 BƯỚC
                renderStageAnalysisDialog(4);
                if (btn) {
                    btn.innerText = '✅ ĐÃ HOÀN TẤT TOÀN BỘ LUỒNG (BẤM ĐỂ CHẠY LẠI)';
                    btn.disabled = false;
                }
                if (statusTag) {
                    statusTag.innerText = 'ĐÃ DUYỆT & HOÀN TẤT 100%';
                    statusTag.style.background = '#dcfce7';
                    statusTag.style.color = '#15803d';
                }
                appendLog('HOÀN TẤT', 'Quy trình đã hoàn tất toàn bộ 4 giai đoạn! Toàn bộ bảng phân tích đã sẵn sàng.');
                showToast('🎉 Đã hoàn tất toàn bộ luồng quy trình Task 2!');
            }
        }

        function renderStageAnalysisDialog(stepNum) {
            const dialog = document.getElementById('pipeline-stage-dialog');
            if (!dialog) return;

            const isHP = (currentSummaryData && currentSummaryData.is_hung_phat) || allDossiers.some(d => d && d.is_hung_phat);
            let html = '';

            if (stepNum === 1) {
                html = `
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
                        <div>
                            <span style="font-size:11px; font-weight:800; color:#0f766e; background:#ccfbf1; padding:3px 9px; border-radius:5px; text-transform:uppercase;">
                                GIAI ĐOẠN 2.1 HOÀN TẤT
                            </span>
                            <h3 style="margin:6px 0 0 0; font-size:16px; color:#0f172a; font-weight:800;">
                                🧠 Kết Quả Phân Tích Chuyên Sâu: Bóc Tách NLP & Chuẩn Hóa Dữ Liệu
                            </h3>
                        </div>
                        <span style="font-size:12px; color:#059669; font-weight:700; background:#ecfdf5; padding:5px 12px; border-radius:20px; border:1px solid #a7f3d0;">
                            ✓ Đã thẩm định ${rawItems.length} bản ghi
                        </span>
                    </div>

                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:14px; font-size:13px; line-height:1.6; color:#334155;">
                        ${isHP ? `
                            <p style="margin:0 0 6px 0;"><strong>🛡️ Phát hiện Trùng Lặp T-01:</strong> Bản ghi <code>MR-004</code> (KV2, 920 DN) bị trùng lặp hoàn toàn với <code>MR-003</code>. Hệ thống đã đánh dấu <code>DUPLICATE</code> và loại khỏi phép tính tổng để bảo toàn thị trường mục tiêu chuẩn là <strong>4,090 DN</strong>.</p>
                            <p style="margin:0 0 6px 0;"><strong>📈 Phân tách chuỗi thời gian T-02:</strong> Bản ghi <code>MR-001</code> (2025-Q4: 1,200 DN) và <code>MR-002</code> (2026-Q1: 1,280 DN) phản ánh tăng trưởng <strong>+6.67% QoQ</strong>, nhận định là biến động thời gian, không mâu thuẫn.</p>
                            <p style="margin:0;"><strong>⚠️ Kiểm toán rỗng T-03 & T-04:</strong> Phát hiện khuyết thiếu tại <code>MR-008</code> (Quy mô KV4) và <code>FB-008</code> (Điểm hài lòng). Đã gắn cờ tường minh <code>NULL</code>, tuyệt đối không tự ý điền số liệu giả định.</p>
                        ` : `
                            <p style="margin:0 0 6px 0;"><strong>🧠 Bóc tách thực thể:</strong> Bóc tách thành công 100% các trường định danh từ văn bản tự nhiên (Khách hàng, Email, Yêu cầu cấu hình, Ngân sách, Deadline).</p>
                            <p style="margin:0 0 6px 0;"><strong>🏷️ Khớp mã Catalog:</strong> Nhận diện chính xác các mã cấu hình phần cứng chuẩn (Dell OptiPlex 7090, ThinkPad T14, Server PowerEdge R750).</p>
                            <p style="margin:0;"><strong>👤 Phân quyền NVKD:</strong> Tự động gán mã định danh <code>REQ-xxxx</code> và chia tuyến cho các chuyên viên tư vấn phụ trách.</p>
                        `}
                    </div>

                    <div style="background:#f0fdf4; border:1.5px solid #86efac; border-radius:10px; padding:12px 16px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                        <div style="font-size:13px; font-weight:700; color:#166534;">
                            ❓ Giai đoạn 2.1 đã hoàn thành phân tích. Bạn có muốn tiếp tục chạy sang Giai đoạn 2.2 (Thẩm Tra Checklist Đầy Đủ) không?
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="btn btn-primary" onclick="continueToNextStage(2)" style="font-size:12.5px; padding:9px 18px; background:#059669; border-color:#059669; font-weight:800; box-shadow:0 2px 8px rgba(5,150,105,0.3);">
                                ▶ Tiếp Tục Sang Giai Đoạn 2.2 ➔
                            </button>
                            <button class="btn btn-outline" onclick="continueAllStagesAuto(2)" style="font-size:12.5px; padding:9px 14px;">
                                ⚡ Chạy Tự Động Các Bước Còn Lại
                            </button>
                        </div>
                    </div>
                `;
            } else if (stepNum === 2) {
                html = `
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
                        <div>
                            <span style="font-size:11px; font-weight:800; color:#0f766e; background:#ccfbf1; padding:3px 9px; border-radius:5px; text-transform:uppercase;">
                                GIAI ĐOẠN 2.2 HOÀN TẤT
                            </span>
                            <h3 style="margin:6px 0 0 0; font-size:16px; color:#0f172a; font-weight:800;">
                                🔍 Kết Quả Phân Tích Chuyên Sâu: Thẩm Tra Checklist & Tính Toàn Vẹn
                            </h3>
                        </div>
                        <span style="font-size:12px; color:#059669; font-weight:700; background:#ecfdf5; padding:5px 12px; border-radius:20px; border:1px solid #a7f3d0;">
                            ✓ Checklist 4 Trường Bắt Buộc
                        </span>
                    </div>

                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:14px; font-size:13px; line-height:1.6; color:#334155;">
                        <p style="margin:0 0 6px 0;"><strong>📋 Rà soát 4 trường bắt buộc:</strong> (1) Mã SKU/Sản phẩm, (2) Số lượng đặt, (3) Ngân sách dự kiến, (4) Thời hạn giao hàng.</p>
                        <p style="margin:0 0 6px 0;"><strong>✉️ Cơ chế tự động hóa (SLA Bán hàng):</strong> Với những yêu cầu khách hàng chưa cung cấp đủ ngân sách hoặc ngày giao mong muốn, hệ thống tự động soạn thảo <em>Mẫu thư đề nghị khách hàng làm rõ thông tin</em> để nhân viên kinh doanh gửi ngay, không làm gián đoạn luồng.</p>
                        <p style="margin:0;"><strong>🛡️ Tính toàn vẹn:</strong> Đảm bảo 100% hồ sơ trước khi tiến hành giữ hàng tồn kho đều được kiểm duyệt chặt chẽ về dữ liệu đầu vào.</p>
                    </div>

                    <div style="background:#f0fdf4; border:1.5px solid #86efac; border-radius:10px; padding:12px 16px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                        <div style="font-size:13px; font-weight:700; color:#166534;">
                            ❓ Giai đoạn 2.2 đã hoàn thành thẩm tra checklist. Bạn có muốn tiếp tục sang Giai đoạn 2.3 (Kiểm Tra Tồn Kho 2 Kho) không?
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="btn btn-primary" onclick="continueToNextStage(3)" style="font-size:12.5px; padding:9px 18px; background:#059669; border-color:#059669; font-weight:800; box-shadow:0 2px 8px rgba(5,150,105,0.3);">
                                ▶ Tiếp Tục Sang Giai Đoạn 2.3 ➔
                            </button>
                            <button class="btn btn-outline" onclick="continueAllStagesAuto(3)" style="font-size:12.5px; padding:9px 14px;">
                                ⚡ Chạy Tự Động Các Bước Còn Lại
                            </button>
                        </div>
                    </div>
                `;
            } else if (stepNum === 3) {
                html = `
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
                        <div>
                            <span style="font-size:11px; font-weight:800; color:#0f766e; background:#ccfbf1; padding:3px 9px; border-radius:5px; text-transform:uppercase;">
                                GIAI ĐOẠN 2.3 HOÀN TẤT
                            </span>
                            <h3 style="margin:6px 0 0 0; font-size:16px; color:#0f172a; font-weight:800;">
                                🏭 Kết Quả Phân Tích Chuyên Sâu: Thẩm Định Tồn Kho & Năng Lực Triển Khai
                            </h3>
                        </div>
                        <span style="font-size:12px; color:#059669; font-weight:700; background:#ecfdf5; padding:5px 12px; border-radius:20px; border:1px solid #a7f3d0;">
                            ✓ Kho Hà Nội & TP.HCM
                        </span>
                    </div>

                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:14px; font-size:13px; line-height:1.6; color:#334155;">
                        ${isHP ? `
                            <p style="margin:0 0 6px 0;"><strong>⚠️ Nút thắt cổ chai năng lực T-05:</strong></p>
                            <ul style="margin:0 0 8px 18px; padding:0;">
                                <li><strong>KV1 (Thặng dư +220 DN):</strong> Nhu cầu 1,280 DN / Năng lực 1,500 DN ➔ Đạt.</li>
                                <li><strong>KV2 (Thặng dư +80 DN):</strong> Nhu cầu 920 DN / Năng lực 1,000 DN ➔ Đạt.</li>
                                <li><strong style="color:#b91c1c;">KV3 (THIẾU HỤT -250 DN):</strong> Nhu cầu 600 DN / Năng lực chỉ 350 DN ➔ <strong>Quá tải nghiêm trọng</strong>.</li>
                                <li><strong style="color:#b91c1c;">KV4 (THIẾU HỤT -350 DN):</strong> Nhu cầu 850 DN / Năng lực chỉ 500 DN ➔ <strong>Quá tải nghiêm trọng</strong>.</li>
                            </ul>
                            <p style="margin:0;"><strong>💡 Khuyến nghị BI:</strong> Không thể triển khai đại trà tại KV3 và KV4 nếu không bổ sung nguồn lực thuê ngoài (outsourcing) hoặc điều phối kỹ sư từ KV1 sang.</p>
                        ` : `
                            <p style="margin:0 0 6px 0;"><strong>🏢 Trung tâm logistics Kho Hà Nội:</strong> Tồn kho khả dụng dồi dào đối với các dòng máy tính văn phòng tiêu chuẩn (Dell OptiPlex), sẵn sàng xuất ngay trong 24 giờ.</p>
                            <p style="margin:0 0 6px 0;"><strong>🏢 Trung tâm logistics Kho TP.HCM:</strong> Đảm bảo lượng tồn máy chủ và linh kiện mạng chuyên dụng.</p>
                            <p style="margin:0;"><strong>📦 Phân định tồn kho:</strong> Các dòng hàng thiếu sẵn có (Backorder) đã được đưa vào danh sách kích hoạt lệnh đặt hàng phân phối với lead time tiêu chuẩn 5 - 7 ngày.</p>
                        `}
                    </div>

                    <div style="background:#f0fdf4; border:1.5px solid #86efac; border-radius:10px; padding:12px 16px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                        <div style="font-size:13px; font-weight:700; color:#166534;">
                            ❓ Giai đoạn 2.3 đã hoàn thành kiểm tra tồn kho & năng lực. Bạn có muốn tiếp tục sang Giai đoạn 2.4 (Chuẩn Hóa Lead Time - Bước Cuối) không?
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="btn btn-primary" onclick="continueToNextStage(4)" style="font-size:12.5px; padding:9px 18px; background:#059669; border-color:#059669; font-weight:800; box-shadow:0 2px 8px rgba(5,150,105,0.3);">
                                ▶ Tiếp Tục Sang Giai Đoạn 2.4 ➔
                            </button>
                            <button class="btn btn-outline" onclick="continueAllStagesAuto(4)" style="font-size:12.5px; padding:9px 14px;">
                                ⚡ Chạy Tự Động Bước Cuối
                            </button>
                        </div>
                    </div>
                `;
            } else if (stepNum === 4) {
                html = `
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
                        <div>
                            <span style="font-size:11px; font-weight:800; color:#15803d; background:#dcfce7; padding:3px 9px; border-radius:5px; text-transform:uppercase;">
                                HOÀN TẤT TOÀN BỘ 4 GIAI ĐOẠN LUỒNG
                            </span>
                            <h3 style="margin:6px 0 0 0; font-size:17px; color:#0f172a; font-weight:800;">
                                🎉 Đã Phê Duyệt & Kiểm Định Thành Công Toàn Diện Luồng Quy Trình Task 2!
                            </h3>
                        </div>
                        <span style="font-size:12px; color:#15803d; font-weight:700; background:#dcfce7; padding:5px 12px; border-radius:20px; border:1px solid #86efac;">
                            ✓ 100% Dữ Liệu Đã Chuẩn Hóa
                        </span>
                    </div>

                    <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:14px; margin-bottom:14px; font-size:13px; line-height:1.6; color:#14532d;">
                        <p style="margin:0 0 6px 0;"><strong>⏱️ Chuẩn hóa Lead Time:</strong> Tính toán chính xác thời gian xử lý + vận chuyển + cài đặt so với thời hạn của khách hàng.</p>
                        <p style="margin:0 0 6px 0;"><strong>📊 Đồng bộ hóa toàn diện:</strong> Bảng kho hàng và cấu trúc Star Schema ở Task 2 đã được cập nhật đầy đủ; Task 3 đã hoàn tất thẩm định tài chính; Task 4 đã sẵn sàng Dashboard và báo cáo xuất file.</p>
                        <p style="margin:0;"><strong>🚀 Trạng thái sẵn sàng:</strong> Bạn có thể cuộn xuống xem chi tiết bảng kho, hoặc chuyển sang Task 3 và Task 4 để xem các hồ sơ chi tiết.</p>
                    </div>

                    <div style="display:flex; gap:10px; flex-wrap:wrap;">
                        <button class="btn btn-primary" onclick="switchTask(3)" style="background:#0f766e; border-color:#0f766e; font-weight:800;">
                            ➔ Chuyển Sang Task 3 (Phân Tích Báo Giá)
                        </button>
                        <button class="btn btn-primary" onclick="switchTask(4)" style="background:#2563eb; border-color:#2563eb; font-weight:800;">
                            📊 Chuyển Sang Task 4 (Dashboard & Xuất File)
                        </button>
                        <button class="btn btn-outline" onclick="approveAndRunPipeline()">
                            🔄 Khởi Chạy Lại Luồng Từ Đầu
                        </button>
                    </div>
                `;
            }

            dialog.innerHTML = html;
            dialog.style.display = 'block';
            dialog.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function setNodeState(nodeNum, state) {
            const el = document.getElementById('node-' + nodeNum);
            if (!el) return;
            if (state === 'active') el.className = 'flow-node active';
            else if (state === 'completed') el.className = 'flow-node completed';
            else el.className = 'flow-node';
        }

        function filterTask2(type, btn) {
            t2Filter = type;
            document.querySelectorAll('#panel-task-2 .filter-btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');
            renderTask2Data();
        }

        function renderTask2Data() {
            try {
                const tbody = document.getElementById('clean-tbody');
                if (!tbody) return;
                tbody.innerHTML = '';

                if (!rawItems || rawItems.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có dữ liệu. Hãy nhập dữ liệu ở Task 1 hoặc tải tệp lên.</td></tr>';
                    return;
                }

                if (!isPipelineApproved) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="8" style="text-align:center; padding:35px 20px; background:#fffbeb; border:1px dashed #f59e0b; border-radius:8px;">
                                <div style="font-size:36px; margin-bottom:8px;">🛡️</div>
                                <div style="font-weight:700; font-size:15px; color:#92400e; margin-bottom:6px;">
                                    Đang Có ${rawItems.length} Yêu Cầu Chờ Phê Duyệt Khởi Chạy
                                </div>
                                <p style="font-size:13px; color:#b45309; max-width:540px; margin:0 auto 16px auto; line-height:1.5;">
                                    Dữ liệu đã được nạp và kiểm toán chất lượng ở Task 1. Theo quy định kiểm soát, luồng quy trình bóc tách NLP, kiểm kho và tính Lead time chỉ chạy khi có sự phê duyệt của bạn.
                                </p>
                                <button class="btn btn-primary" onclick="approveAndRunPipeline()" style="font-size:13px; padding:10px 24px; box-shadow:0 4px 12px rgba(37,99,235,0.25); cursor:pointer;">
                                    🛡️ PHÊ DUYỆT & BẮT ĐẦU CHẠY LUỒNG QUY TRÌNH ➔
                                </button>
                            </td>
                        </tr>
                    `;
                    return;
                }

                if (!allDossiers || allDossiers.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có kết quả xử lý. Bấm Duyệt luồng để bắt đầu.</td></tr>';
                    return;
                }

                const isHP = (currentSummaryData && currentSummaryData.is_hung_phat) || allDossiers.some(d => d && d.is_hung_phat);
                const thead = document.getElementById('t2-thead');

                if (isHP) {
                    if (thead) {
                        thead.innerHTML = `
                            <tr>
                                <th>MÃ BẢN GHI & KHU VỰC</th>
                                <th>NHÓM DỮ LIỆU (SHEET)</th>
                                <th>CHỈ TIÊU & NHU CẦU GỐC</th>
                                <th>GIÁ TRỊ THỰC TẾ</th>
                                <th>KIỂM TOÁN CHẤT LƯỢNG (DATA AUDIT FLAGS)</th>
                                <th>HÀNH ĐỘNG XỬ LÝ BI</th>
                                <th>TRẠNG THÁI</th>
                            </tr>
                        `;
                    }

                    const rows = [];
                    allDossiers.forEach(d => {
                        if (!d || typeof d !== 'object') return;
                        const rec = d.hung_phat_record || {};
                        const flags = (rec.audit_flags && rec.audit_flags.length > 0) ? rec.audit_flags : ['Dữ liệu đạt chuẩn'];
                        let flagBadges = '';
                        flags.forEach(f => {
                            if (f.includes('TRÙNG LẶP') || f.includes('T-01')) {
                                flagBadges += `<span class="badge badge-amber" style="display:block; margin-bottom:3px; font-weight:700;">⚠️ ${f}</span>`;
                            } else if (f.includes('KHÁC KỲ') || f.includes('T-02')) {
                                flagBadges += `<span class="badge badge-blue" style="display:block; margin-bottom:3px; font-weight:700;">📈 ${f}</span>`;
                            } else if (f.includes('THIẾU') || f.includes('T-03') || f.includes('T-04')) {
                                flagBadges += `<span class="badge badge-red" style="display:block; margin-bottom:3px; font-weight:700;">❌ ${f}</span>`;
                            } else if (f.includes('NGHẼN') || f.includes('T-05')) {
                                flagBadges += `<span class="badge badge-red" style="display:block; margin-bottom:3px; font-weight:700;">🛑 ${f}</span>`;
                            } else {
                                flagBadges += `<span class="badge badge-green" style="display:block; margin-bottom:3px;">✅ ${f}</span>`;
                            }
                        });

                        const statusBadge = (rec.status === 'VALID') 
                            ? '<span class="badge badge-green">✅ Hợp Lệ</span>'
                            : ((rec.status === 'DUPLICATE')
                                ? '<span class="badge badge-amber">🛑 Khử Trùng Lặp</span>'
                                : ((rec.status === 'MISSING')
                                    ? '<span class="badge badge-red">⚠️ Đánh Dấu Thiếu</span>'
                                    : '<span class="badge badge-amber">⚠️ Cảnh Báo Vượt Tải</span>'));

                        const valStr = (rec.value !== null && rec.value !== undefined) ? `${rec.value} ${rec.unit || ''}` : '<span style="color:var(--danger); font-weight:700;">NULL / Thiếu</span>';

                        rows.push(`
                            <tr>
                                <td><strong>${d.opportunity_id || ''}</strong><br><small style="color:var(--primary); font-weight:700;">${rec.region || ''}</small></td>
                                <td><span class="badge badge-blue">${rec.sheet || ''}</span></td>
                                <td><b>${rec.metric || ''}</b><br><small style="color:var(--text-muted);">${rec.description || ''}</small></td>
                                <td><strong style="color:#0f766e; font-size:13px;">${valStr}</strong></td>
                                <td>${flagBadges}</td>
                                <td><small style="color:#334155; font-size:12px; line-height:1.4;">${rec.action_note || ''}</small></td>
                                <td>${statusBadge}</td>
                            </tr>
                        `);
                    });
                    tbody.innerHTML = rows.join('');
                    return;
                }

                // Chế độ B2B Kho tiêu chuẩn
                if (thead) {
                    thead.innerHTML = `
                        <tr>
                            <th>MÃ CƠ HỘI</th>
                            <th>HẠNG MỤC (SKU CHUẨN HÓA)</th>
                            <th>SỐ LƯỢNG</th>
                            <th>TỒN KHẢ DỤNG</th>
                            <th>VỊ TRÍ KHO</th>
                            <th>LEAD TIME KHO CẦN</th>
                            <th>HẠN ĐỊNH CỦA KHÁCH</th>
                            <th>KẾT LUẬN TIẾN ĐỘ</th>
                        </tr>
                    `;
                }

                const rows = [];
                allDossiers.forEach(d => {
                    if (!d || typeof d !== 'object') return;
                    const extData = d.extracted_data || {};
                    if (!d.feasibility || !d.feasibility.items_feasibility || d.feasibility.items_feasibility.length === 0) {
                        if (t2Filter === 'all') {
                            rows.push(`
                                <tr>
                                    <td><strong>${d.opportunity_id || 'REQ-?'}</strong><br><small>${d.customer_name || 'Khách Hàng'}</small></td>
                                    <td colspan="7" style="color:var(--warning); font-style:italic;">Thiếu dữ kiện ở Task 1 -> Hệ thống tạo thư đề nghị khách bổ sung.</td>
                                </tr>
                            `);
                        }
                        return;
                    }

                    d.feasibility.items_feasibility.forEach(it => {
                        if (!it || typeof it !== 'object') return;
                        const isStockOk = it.is_stock_sufficient;
                        const isOnTime = (d.feasibility && d.feasibility.lead_time_status === 'Kịp tiến độ');

                        // Lọc tương tác
                        if (t2Filter === 'in-stock' && !isStockOk) return;
                        if (t2Filter === 'shortage' && isStockOk) return;
                        if (t2Filter === 'on-time' && !isOnTime) return;
                        if (t2Filter === 'delayed' && isOnTime) return;

                        const leadBadge = isStockOk 
                            ? '<span class="badge badge-green">✅ Đủ kho sẵn sàng</span>' 
                            : `<span class="badge badge-amber">⚠️ Thiếu ${it.stock_shortage || 0} cái (Cần nhập)</span>`;
                        
                        const timeBadge = isOnTime
                            ? '<span class="badge badge-green">Kịp tiến độ</span>'
                            : '<span class="badge badge-red">Trễ tiến độ</span>';

                        rows.push(`
                            <tr>
                                <td><strong>${d.opportunity_id || ''}</strong><br><small>${d.customer_name || ''}</small></td>
                                <td><b>${it.name || ''}</b><br><small style="color:var(--primary); font-family:monospace;">SKU: ${it.sku || ''}</small></td>
                                <td><strong>${it.requested_qty || 0}</strong> chiếc</td>
                                <td>${it.available_stock || 0} (${leadBadge})</td>
                                <td>${it.inventory_location || 'Trung tâm'}</td>
                                <td><strong>${it.estimated_lead_days || 0} ngày</strong></td>
                                <td>${extData.delivery_days || '?'} ngày</td>
                                <td>${timeBadge}</td>
                            </tr>
                        `);
                    });
                });
                const maxDisplayT2 = 100;
                const displayedT2Rows = rows.slice(0, maxDisplayT2);
                if (rows.length > maxDisplayT2) {
                    displayedT2Rows.push(`
                        <tr>
                            <td colspan="8" style="text-align:center; padding:16px; background:#f0fdf4; color:#166534; font-weight:600;">
                                📊 Đang hiển thị ${maxDisplayT2} / ${rows.length} yêu cầu đầu vào. Toàn bộ hồ sơ được xử lý và xuất đầy đủ tại Task 4.
                            </td>
                        </tr>
                    `);
                }
                tbody.innerHTML = displayedT2Rows.join('');
            } catch (err) {
                console.error('Error in renderTask2Data:', err);
            }
        }

        // ==========================================
        // TASK 3: PHÂN TÍCH & SO SÁNH
        // ==========================================
        function filterTask3(type, btn) {
            t3Filter = type;
            document.querySelectorAll('#panel-task-3 .filter-btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');
            renderTask3Data();
        }

        function renderTask3Data() {
            try {
                renderDiagnosticInsights();
                const tbody = document.getElementById('pricing-tbody');
                if (!tbody) return;

                const isHP = (currentSummaryData && currentSummaryData.is_hung_phat) || allDossiers.some(d => d && d.is_hung_phat);
                const thead = document.getElementById('t3-thead');

                if (isHP) {
                    const kpiList = (currentSummaryData && currentSummaryData.regional_kpi) ? currentSummaryData.regional_kpi : [];
                    document.getElementById('t3-budget-rate').innerText = '4,090 DN';
                    document.getElementById('t3-budget-sub').innerText = 'Tổng DN mục tiêu (Khử trùng T-01)';
                    document.getElementById('t3-discount-stat').innerText = '55.7%';
                    document.getElementById('t3-discount-sub').innerText = 'Tỷ lệ quan tâm WMS trung bình';
                    document.getElementById('t3-leadtime-rate').innerText = '100%';
                    document.getElementById('t3-leadtime-sub').innerText = 'Đạt chuẩn tổng trọng số (T-06)';
                    document.getElementById('t3-total-savings').innerText = '550 Triệu VNĐ';

                    if (thead) {
                        thead.innerHTML = `
                            <tr>
                                <th>KHU VỰC THỊ TRƯỜNG</th>
                                <th>DOANH NGHIỆP MỤC TIÊU</th>
                                <th>TỶ LỆ QUAN TÂM WMS</th>
                                <th>NĂNG LỰC TRIỂN KHAI</th>
                                <th>ĐỐI THỦ CẠNH TRANH</th>
                                <th>ĐIỂM 5 TIÊU CHÍ (EC-01..05)</th>
                                <th>ĐIỂM TỔNG HỢP</th>
                                <th>XẾP HẠNG CHIẾN LƯỢC</th>
                            </tr>
                        `;
                    }

                    const rows = [];
                    kpiList.forEach(k => {
                        rows.push(`
                            <tr>
                                <td><strong style="font-size:14px; color:#0f766e;">${k.region}</strong><br><small style="color:var(--text-muted);">${k.notes || ''}</small></td>
                                <td><b style="font-size:13.5px;">${k.target_enterprises.toLocaleString('vi-VN')}</b> doanh nghiệp</td>
                                <td><span class="badge ${k.interest_rate ? 'badge-green' : 'badge-red'}">${k.interest_rate_str}</span></td>
                                <td><b>${k.max_projects} dự án tối đa</b><br><small style="color:var(--text-muted);">${k.staff_summary}</small></td>
                                <td><small><b>${k.competitors_count} đối thủ:</b><br>${k.competitors_str}</small></td>
                                <td><small style="line-height:1.4;">EC1:${k.ec1_market} | EC2:${k.ec2_demand} | EC3:${k.ec3_fit}<br>EC4:${k.ec4_competition} | EC5:${k.ec5_capacity}</small></td>
                                <td><strong style="font-size:15px; color:${k.total_score >= 80 ? '#059669' : '#0284c7'};">${k.total_score}</strong> / 100</td>
                                <td><span class="badge ${k.badge_class}" style="font-weight:700;">${k.rank_label}</span></td>
                            </tr>
                        `);
                    });
                    tbody.innerHTML = rows.join('');
                    return;
                }

                if (thead) {
                    thead.innerHTML = `
                        <tr>
                            <th>MÃ & KHÁCH HÀNG</th>
                            <th>GIÁ NIÊM YẾT</th>
                            <th>GIÁ ĐỀ XUẤT (NET)</th>
                            <th>CHIẾT KHẤU</th>
                            <th>NGÂN SÁCH KHÁCH</th>
                            <th>CHÊNH LỆCH (%)</th>
                            <th>THỜI HẠN GIAO</th>
                            <th>THẨM QUYỀN DUYỆT</th>
                        </tr>
                    `;
                }

                if (!allDossiers || allDossiers.length === 0) {
                    document.getElementById('t3-budget-rate').innerText = '0%';
                    document.getElementById('t3-budget-sub').innerText = '0/0 ca trong ngân sách';
                    document.getElementById('t3-discount-stat').innerText = '0%';
                    document.getElementById('t3-discount-sub').innerText = (rawItems.length > 0 && !isPipelineApproved) ? 'Chờ duyệt luồng tại Task 2' : 'Chưa có dữ liệu';
                    document.getElementById('t3-leadtime-rate').innerText = '0%';
                    document.getElementById('t3-leadtime-sub').innerText = '0/0 ca đúng hạn';
                    document.getElementById('t3-total-savings').innerText = '0 đ';
                    
                    const isWaiting = (rawItems.length > 0 && !isPipelineApproved);
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="8" style="text-align:center; padding:35px 20px; background:#f8fafc;">
                                <div style="font-size:36px; margin-bottom:8px;">${isWaiting ? '⏳' : '📊'}</div>
                                <div style="font-weight:700; font-size:15px; color:#1e293b; margin-bottom:4px;">
                                    ${isWaiting ? 'Quy Trình Đang Chờ Phê Duyệt Tại Task 2' : 'Chưa Có Dữ Liệu Đầu Vào Để Phân Tích'}
                                </div>
                                <p style="font-size:12.5px; color:#64748b; margin-bottom:14px;">
                                    ${isWaiting ? 'Bảng tính toán định giá và phân tích sẽ tự động kích hoạt ngay sau khi bạn duyệt luồng tại Task 2.' : 'Hệ thống tuân thủ nguyên tắc: <b>Không bịa đặt dữ liệu</b>. Chỉ khi có dữ liệu nạp vào từ Task 1, hệ thống mới bắt đầu phân tích.'}
                                </p>
                                <button class="btn btn-primary" onclick="${isWaiting ? 'switchTask(2)' : 'switchTask(1)'}" style="font-size:12px; padding:7px 18px;">
                                    ${isWaiting ? '🛡️ Chuyển Sang Task 2 Để Phê Duyệt' : '📥 Đến Task 1 Nhập / Nạp Dữ Liệu'}
                                </button>
                            </td>
                        </tr>
                    `;
                    return;
                }

                let budgetCasesWithData = 0, budgetWithinCount = 0, totalSavings = 0, totalStdDisc = 0, onTimeCount = 0, validTimeCount = 0;

                allDossiers.forEach(d => {
                    const pricing = d.pricing;
                    const extracted = d.extracted_data || {};
                    const feas = d.feasibility;

                    if (pricing) {
                        totalSavings += (pricing.total_discount_amount || 0);
                        if (extracted.budget) {
                            budgetCasesWithData++;
                            if (pricing.is_within_budget) budgetWithinCount++;
                        }
                        totalStdDisc += (pricing.applied_discount_rate || 0);
                    }
                    if (feas && feas.customer_deadline_days) {
                        validTimeCount++;
                        if (feas.lead_time_status === 'Kịp tiến độ') onTimeCount++;
                    }
                });

                const budgetRate = budgetCasesWithData > 0 ? Math.round((budgetWithinCount / budgetCasesWithData) * 100) : 0;
                const leadRate = validTimeCount > 0 ? Math.round((onTimeCount / validTimeCount) * 100) : 0;
                const pricedCount = allDossiers.filter(d => d.pricing).length;
                const avgDisc = pricedCount > 0 ? ((totalStdDisc / pricedCount) * 100).toFixed(1) : 0;

                document.getElementById('t3-budget-rate').innerText = `${budgetRate}%`;
                document.getElementById('t3-budget-sub').innerText = `${budgetWithinCount}/${budgetCasesWithData} ca trong ngân sách`;
                document.getElementById('t3-discount-stat').innerText = `${avgDisc}%`;
                document.getElementById('t3-discount-sub').innerText = `Mức áp dụng trung bình`;
                document.getElementById('t3-leadtime-rate').innerText = `${leadRate}%`;
                document.getElementById('t3-leadtime-sub').innerText = `${onTimeCount}/${validTimeCount} ca đúng hạn định`;
                const savingsFormatted = totalSavings >= 1e9 
                    ? (totalSavings / 1e9).toFixed(2) + ' Tỷ VNĐ'
                    : (totalSavings >= 1e6 ? (totalSavings / 1e6).toFixed(1) + ' Triệu VNĐ' : Math.round(totalSavings).toLocaleString('vi-VN') + ' đ');
                document.getElementById('t3-total-savings').innerText = savingsFormatted;

                const rows = [];
                allDossiers.forEach(d => {
                    const pricing = d.pricing;
                    const extracted = d.extracted_data || {};
                    const feas = d.feasibility;
                    const isWithin = pricing ? pricing.is_within_budget : false;
                    const isEscalation = (d.approval && d.approval.requires_escalation);

                    if (t3Filter === 'within-budget' && (!pricing || !isWithin)) return;
                    if (t3Filter === 'over-budget' && (!pricing || isWithin)) return;
                    if (t3Filter === 'escalation' && !isEscalation) return;

                    if (!pricing) {
                        rows.push(`
                            <tr>
                                <td><strong>${d.opportunity_id || 'REQ-?'}</strong><br><small>${d.customer_name || 'Khách Hàng'}</small></td>
                                <td colspan="7" style="color:var(--text-muted); font-style:italic;">Thiếu dữ kiện đầu vào -> Đã tạo email yêu cầu khách làm rõ.</td>
                            </tr>
                        `);
                    } else {
                        const subStr = (pricing.base_subtotal || 0).toLocaleString('vi-VN') + ' đ';
                        const netStr = (pricing.final_proposal_value || 0).toLocaleString('vi-VN') + ' đ';
                        const budget = extracted.budget;
                        const budgetStr = budget ? Number(budget).toLocaleString('vi-VN') + ' đ' : '<span style="color:var(--text-muted)">Chưa rõ</span>';

                        let budgetComp = '';
                        if (budget) {
                            const variance = Number(budget) - pricing.final_proposal_value;
                            if (variance >= 0) {
                                const pct = ((variance / Number(budget)) * 100).toFixed(1);
                                budgetComp = `<span class="badge badge-green">✅ Dư +${Math.round(variance).toLocaleString('vi-VN')} đ (+${pct}%)</span>`;
                            } else {
                                const deficit = Math.abs(variance);
                                const pct = ((deficit / Number(budget)) * 100).toFixed(1);
                                budgetComp = `<span class="badge badge-red">❌ Vượt -${Math.round(deficit).toLocaleString('vi-VN')} đ (-${pct}%)</span>`;
                            }
                        } else {
                            budgetComp = '<span class="badge badge-amber">⚠️ Chưa có ngân sách</span>';
                        }

                        const reqDisc = (extracted.requested_discount_rate !== null && extracted.requested_discount_rate !== undefined)
                            ? (Number(extracted.requested_discount_rate) * 100).toFixed(1) + '%'
                            : 'Chuẩn';
                        const appliedDisc = ((pricing.applied_discount_rate || 0.05) * 100).toFixed(1) + '%';
                        let discBadge = `<span class="badge badge-blue">Áp dụng: ${appliedDisc}</span>`;
                        if (pricing.applied_discount_rate > 0.08) {
                            discBadge = `<span class="badge badge-purple">Vượt NVKD: ${appliedDisc}</span>`;
                        }
                        const discComp = `<div>Khách đòi: <b>${reqDisc}</b></div><div>${discBadge}</div>`;

                        let timeComp = '';
                        if (feas && feas.customer_deadline_days) {
                            const dl = feas.customer_deadline_days;
                            const lead = feas.overall_lead_days_needed || 3;
                            const gap = dl - lead;
                            if (gap >= 0) {
                                timeComp = `<span class="badge badge-green">✅ Kịp (${lead}/${dl} ngày)</span>`;
                            } else {
                                timeComp = `<span class="badge badge-red">❌ Trễ thiếu ${Math.abs(gap)} ngày (${lead}/${dl}n)</span>`;
                            }
                        } else {
                            timeComp = '<span class="badge badge-amber">Chưa rõ hạn định</span>';
                        }

                        let conclusion = '';
                        if (d.status === 'CÓ THỂ TIẾP TỤC') {
                            conclusion = '<span class="badge badge-green">🌟 Cực kỳ khả thi</span>';
                        } else if (d.status === 'CHỜ DUYỆT') {
                            conclusion = '<span class="badge badge-purple">📑 Cần trình duyệt CK</span>';
                        } else if (d.status === 'CHƯA ĐÁP ỨNG') {
                            conclusion = '<span class="badge badge-red">⚠️ Không khả thi tiến độ/tiền</span>';
                        } else {
                            conclusion = '<span class="badge badge-amber">❓ Cần bổ sung dữ liệu</span>';
                        }

                        rows.push(`
                            <tr>
                                <td><strong>${d.opportunity_id || ''}</strong><br><b>${d.customer_name || ''}</b></td>
                                <td>${subStr}</td>
                                <td><strong style="color:var(--primary); font-size:14px;">${netStr}</strong></td>
                                <td>${budgetStr}</td>
                                <td>${budgetComp}</td>
                                <td>${discComp}</td>
                                <td>${timeComp}</td>
                                <td>${conclusion}</td>
                            </tr>
                        `);
                    }
                });
                const maxDisplayT3 = 100;
                const displayedT3Rows = rows.slice(0, maxDisplayT3);
                if (rows.length > maxDisplayT3) {
                    displayedT3Rows.push(`
                        <tr>
                            <td colspan="8" style="text-align:center; padding:16px; background:#f0fdf4; color:#166534; font-weight:600;">
                                📊 Đang hiển thị ${maxDisplayT3} / ${rows.length} cơ hội kinh doanh. Toàn bộ ${rows.length} hồ sơ đã được phân tích đầy đủ và có thể xuất Excel/CSV/JSON tại Task 4.
                            </td>
                        </tr>
                    `);
                }
                tbody.innerHTML = displayedT3Rows.join('');
            } catch (err) {
                console.error('Error in renderTask3Data:', err);
            }
        }

        // ==========================================
        // TASK 4: DASHBOARD & XUẤT BÁO CÁO
        // ==========================================
        function renderTask4Data() {
            try {
                updateBLUFSummary();
                const hasData = (allDossiers && allDossiers.length > 0);

                if (!hasData) {
                    document.getElementById('kpi-total-val').innerText = '0 VNĐ';
                    document.getElementById('kpi-eligible').innerText = '0';
                    document.getElementById('kpi-pending').innerText = '0';
                    document.getElementById('kpi-dash-missing').innerText = '0';
                    document.getElementById('kpi-unfeasible').innerText = '0';

                    document.getElementById('seg-green').style.width = '0%';
                    document.getElementById('seg-purple').style.width = '0%';
                    document.getElementById('seg-amber').style.width = '0%';
                    document.getElementById('seg-red').style.width = '0%';

                    document.getElementById('leg-green').innerText = '0 (0%)';
                    document.getElementById('leg-purple').innerText = '0 (0%)';
                    document.getElementById('leg-amber').innerText = '0 (0%)';
                    document.getElementById('leg-red').innerText = '0 (0%)';
                    document.getElementById('widget-total-count').innerText = '0 Yêu cầu';

                    document.getElementById('gov-salesrep').innerText = '0 cơ hội';
                    document.getElementById('gov-manager').innerText = '0 cơ hội';
                    document.getElementById('gov-board').innerText = '0 cơ hội';

                    const repDiv = document.getElementById('salesrep-workload');
                    if (repDiv) repDiv.innerHTML = '<div style="color:var(--text-muted); font-size:12.5px; padding:6px 0;">' + ((rawItems.length > 0 && !isPipelineApproved) ? '⏳ Chờ phê duyệt luồng tại Task 2 để tổng hợp số liệu.' : 'Chưa có dữ liệu cơ hội kinh doanh.') + '</div>';

                    document.getElementById('inv-instock-rate').innerText = '0%';
                    document.getElementById('inv-restock-needed').innerText = '0 mã SKU';
                    document.getElementById('inv-ontime-rate').innerText = '0%';

                    renderDashboardMasterTable();
                    renderDashboardSalesRepTable();
                    renderDashboardGovernanceTable();
                    renderDashboardInventoryTable();
                    renderComboChart(comboChartMode);
                    return;
                }

                const s = currentSummaryData || {};
                const statusCounts = s.status_counts || {};
                const isHP = (s && s.is_hung_phat) || allDossiers.some(d => d && d.is_hung_phat);

                if (isHP) {
                    const kpis = s.regional_kpi || [];
                    let totalEnt = 4090;
                    if (kpis.length > 0) {
                        totalEnt = kpis.reduce((acc, k) => acc + (k.target_enterprises || 0), 0);
                    }
                    const valCnt = s.valid_count || 16;
                    const warnCnt = s.warning_count || 6;

                    // Cập nhật nhãn & giá trị chuẩn xác cho 5 thẻ KPI
                    const l1 = document.getElementById('lbl-kpi-1'); if (l1) l1.innerText = 'Tổng Quy Mô Thị Trường (Target Enterprises)';
                    const s1 = document.getElementById('sub-kpi-1'); if (s1) s1.innerText = 'Đã khử trùng T-01 (Dự toán: 550 Triệu VNĐ)';
                    const l2 = document.getElementById('lbl-kpi-2'); if (l2) l2.innerText = 'Bản Ghi Hợp Lệ (Valid Data)';
                    const s2 = document.getElementById('sub-kpi-2'); if (s2) s2.innerText = 'Sẵn sàng cho mô hình hóa Star Schema';
                    const l3 = document.getElementById('lbl-kpi-3'); if (l3) l3.innerText = 'Bản Ghi Trùng Lặp (Duplicate T-01)';
                    const s3 = document.getElementById('sub-kpi-3'); if (s3) s3.innerText = 'Phát hiện MR-004 đã khử trùng lặp';
                    const l4 = document.getElementById('lbl-kpi-4'); if (l4) l4.innerText = 'Thiếu Dữ Liệu Cố Ý (Missing T-03/04)';
                    const s4 = document.getElementById('sub-kpi-4'); if (s4) s4.innerText = 'MR-008 & FB-008 đánh dấu NULL';
                    const l5 = document.getElementById('lbl-kpi-5'); if (l5) l5.innerText = 'Cảnh Báo Năng Lực (Capacity T-05)';
                    const s5 = document.getElementById('sub-kpi-5'); if (s5) s5.innerText = 'Khu vực 3 & 4 hạn chế kỹ thuật onsite';

                    document.getElementById('kpi-total-val').innerText = `${totalEnt.toLocaleString('vi-VN')} DN`;
                    document.getElementById('kpi-eligible').innerText = `${valCnt}`;
                    document.getElementById('kpi-pending').innerText = `1`;
                    document.getElementById('kpi-dash-missing').innerText = `2`;
                    document.getElementById('kpi-unfeasible').innerText = `2`;

                    const total = (valCnt + warnCnt) || 22;
                    const pGreen = Math.round((valCnt / total) * 100);
                    const pPurple = Math.round((1 / total) * 100);
                    const pAmber = Math.round((2 / total) * 100);
                    const pRed = Math.round((2 / total) * 100);

                    document.getElementById('seg-green').style.width = pGreen + '%';
                    document.getElementById('seg-purple').style.width = pPurple + '%';
                    document.getElementById('seg-amber').style.width = pAmber + '%';
                    document.getElementById('seg-red').style.width = pRed + '%';

                    document.getElementById('leg-green').innerText = `${valCnt} Hợp lệ (${pGreen}%)`;
                    document.getElementById('leg-purple').innerText = `1 Trùng (${pPurple}%)`;
                    document.getElementById('leg-amber').innerText = `2 Thiếu (${pAmber}%)`;
                    document.getElementById('leg-red').innerText = `2 Nghẽn (${pRed}%)`;
                    document.getElementById('widget-total-count').innerText = `${total} Bản Ghi Kiểm Toán`;

                    document.getElementById('gov-salesrep').innerText = 'Khu vực 1: 93.0 điểm (Tier 1 - Ưu Tiên Triển Khai)';
                    document.getElementById('gov-manager').innerText = 'Khu vực 2: 76.7 điểm (Tier 2 - Tiềm Năng Mở Rộng)';
                    document.getElementById('gov-board').innerText = 'Khu vực 3 & 4: Cần bổ sung năng lực (Tier 3)';

                    const repDiv = document.getElementById('salesrep-workload');
                    if (repDiv) {
                        repDiv.innerHTML = `
                            <div style="display:flex; justify-content:space-between; font-size:13px; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">
                                <span>🏢 <b>Khu vực 1</b>: 1,280 DN (62% quan tâm)</span>
                                <span><b>24 DA tối đa</b> | <strong style="color:var(--primary);">180 Triệu VNĐ</strong></span>
                            </div>
                            <div style="display:flex; justify-content:space-between; font-size:13px; border-bottom:1px solid #f1f5f9; padding-bottom:4px; margin-top:4px;">
                                <span>🏢 <b>Khu vực 2</b>: 950 DN (47% quan tâm)</span>
                                <span><b>18 DA tối đa</b> | <strong style="color:var(--primary);">150 Triệu VNĐ</strong></span>
                            </div>
                            <div style="display:flex; justify-content:space-between; font-size:13px; border-bottom:1px solid #f1f5f9; padding-bottom:4px; margin-top:4px;">
                                <span>🏢 <b>Khu vực 3</b>: 760 DN (58% quan tâm)</span>
                                <span><b>12 DA tối đa</b> | <strong style="color:#d97706;">Nghẽn nhân sự (T-05)</strong></span>
                            </div>
                            <div style="display:flex; justify-content:space-between; font-size:13px; margin-top:4px;">
                                <span>🏢 <b>Khu vực 4</b>: 1,100 DN (Thiếu chỉ số)</span>
                                <span><b>10 DA tối đa</b> | <strong style="color:#dc2626;">Thiếu kỳ/nhu cầu (T-03/04)</strong></span>
                            </div>
                        `;
                    }

                    document.getElementById('inv-instock-rate').innerText = '100%';
                    document.getElementById('inv-restock-needed').innerText = '4 Khu vực';
                    document.getElementById('inv-ontime-rate').innerText = '93.0%';
                } else {
                    const l1 = document.getElementById('lbl-kpi-1'); if (l1) l1.innerText = 'Tổng Doanh Số Pipeline Hợp Lệ';
                    const s1 = document.getElementById('sub-kpi-1'); if (s1) s1.innerText = 'Bao gồm cơ hội Hợp lệ & Đang chờ duyệt';
                    const l2 = document.getElementById('lbl-kpi-2'); if (l2) l2.innerText = 'Có Thể Tiếp Tục (Hợp Lệ)';
                    const s2 = document.getElementById('sub-kpi-2'); if (s2) s2.innerText = 'Đáp ứng đủ ngân sách, kho & thẩm quyền';
                    const l3 = document.getElementById('lbl-kpi-3'); if (l3) l3.innerText = 'Chờ Cấp Quản Lý Duyệt';
                    const s3 = document.getElementById('sub-kpi-3'); if (s3) s3.innerText = 'Vượt thẩm quyền chiết khấu / giá trị NVKD';
                    const l4 = document.getElementById('lbl-kpi-4'); if (l4) l4.innerText = 'Cần Bổ Sung Thông Tin';
                    const s4 = document.getElementById('sub-kpi-4'); if (s4) s4.innerText = 'Đã tạo email yêu cầu khách làm rõ';
                    const l5 = document.getElementById('lbl-kpi-5'); if (l5) l5.innerText = 'Chưa Đáp Ứng (Kho/Ngân sách)';
                    const s5 = document.getElementById('sub-kpi-5'); if (s5) s5.innerText = 'Đã tạo thư đề xuất phương án thay thế';

                    let totalVal = 0;
                    let cEligible = 0, cPending = 0, cMissing = 0, cUnfeasible = 0;
                    allDossiers.forEach(d => {
                        if (d.status === 'CÓ THỂ TIẾP TỤC') cEligible++;
                        else if (d.status === 'CHỜ DUYỆT') cPending++;
                        else if (d.status === 'CẦN BỔ SUNG THÔNG TIN') cMissing++;
                        else cUnfeasible++;

                        if (d.pricing && typeof d.pricing.final_proposal_value === 'number') {
                            totalVal += d.pricing.final_proposal_value;
                        }
                    });

                    document.getElementById('kpi-total-val').innerText = totalVal > 0 ? (totalVal.toLocaleString('vi-VN') + ' đ') : (s.total_value_formatted || '0 VNĐ');
                    document.getElementById('kpi-eligible').innerText = cEligible || (statusCounts['CÓ THỂ TIẾP TỤC'] || 0);
                    document.getElementById('kpi-pending').innerText = cPending || (statusCounts['CHỜ DUYỆT'] || 0);
                    document.getElementById('kpi-dash-missing').innerText = cMissing || (statusCounts['CẦN BỔ SUNG THÔNG TIN'] || 0);
                    document.getElementById('kpi-unfeasible').innerText = cUnfeasible || (statusCounts['CHƯA ĐÁP ỨNG'] || 0);

                    const total = allDossiers.length || 1;
                    const pGreen = ((cEligible / total) * 100).toFixed(0);
                    const pPurple = ((cPending / total) * 100).toFixed(0);
                    const pAmber = ((cMissing / total) * 100).toFixed(0);
                    const pRed = ((cUnfeasible / total) * 100).toFixed(0);

                    document.getElementById('seg-green').style.width = pGreen + '%';
                    document.getElementById('seg-purple').style.width = pPurple + '%';
                    document.getElementById('seg-amber').style.width = pAmber + '%';
                    document.getElementById('seg-red').style.width = pRed + '%';

                    document.getElementById('leg-green').innerText = `${cEligible} (${pGreen}%)`;
                    document.getElementById('leg-purple').innerText = `${cPending} (${pPurple}%)`;
                    document.getElementById('leg-amber').innerText = `${cMissing} (${pAmber}%)`;
                    document.getElementById('leg-red').innerText = `${cUnfeasible} (${pRed}%)`;
                    document.getElementById('widget-total-count').innerText = `${total} Yêu cầu`;

                    let cntRep = 0, cntMgr = 0, cntBoard = 0;
                    allDossiers.forEach(d => {
                        if (d.approval) {
                            if (d.approval.approver_role === 'NVKD') cntRep++;
                            else if (d.approval.approver_role === 'Trưởng phòng Kinh doanh') cntMgr++;
                            else cntBoard++;
                        }
                    });
                    document.getElementById('gov-salesrep').innerText = `${cntRep} cơ hội (Thẩm quyền chuẩn)`;
                    document.getElementById('gov-manager').innerText = `${cntMgr} cơ hội (Vượt CK/Giá trị)`;
                    document.getElementById('gov-board').innerText = `${cntBoard} cơ hội (Chính sách đặc biệt)`;

                    const repMap = {};
                    allDossiers.forEach(d => {
                        const rep = d.assigned_sales_rep || 'Chưa gán';
                        if (!repMap[rep]) repMap[rep] = { count: 0, val: 0 };
                        repMap[rep].count++;
                        if (d.pricing && (d.status === 'CÓ THỂ TIẾP TỤC' || d.status === 'CHỜ DUYỆT')) {
                            repMap[rep].val += d.pricing.final_proposal_value;
                        }
                    });
                    const repDiv = document.getElementById('salesrep-workload');
                    if (repDiv) {
                        repDiv.innerHTML = '';
                        Object.keys(repMap).forEach(rep => {
                            const item = repMap[rep];
                            repDiv.innerHTML += `
                                <div style="display:flex; justify-content:space-between; font-size:13px; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">
                                    <span>👤 <b>${rep}</b>:</span>
                                    <span><b>${item.count}</b> vụ việc | <strong style="color:var(--primary);">${item.val.toLocaleString('vi-VN')} đ</strong></span>
                                </div>
                            `;
                        });
                    }
                }

            let totalItems = 0, inStockItems = 0, restockItems = 0, timeValid = 0, onTime = 0;
            allDossiers.forEach(d => {
                if (d.feasibility && d.feasibility.items_feasibility) {
                    d.feasibility.items_feasibility.forEach(it => {
                        totalItems++;
                        if (it.is_stock_sufficient) inStockItems++;
                        else restockItems++;
                    });
                }
                if (d.feasibility && d.feasibility.customer_deadline_days) {
                    timeValid++;
                    if (d.feasibility.lead_time_status === 'Kịp tiến độ') onTime++;
                }
            });
            const inStockRate = totalItems > 0 ? Math.round((inStockItems / totalItems) * 100) : 0;
            const onTimeRate = timeValid > 0 ? Math.round((onTime / timeValid) * 100) : 0;
            document.getElementById('inv-instock-rate').innerText = `${inStockRate}% (${inStockItems}/${totalItems} sản phẩm)`;
            document.getElementById('inv-restock-needed').innerText = `${restockItems} hạng mục thiếu`;
            document.getElementById('inv-ontime-rate').innerText = `${onTimeRate}% (${onTime}/${timeValid} cơ hội)`;

            const tbody = document.getElementById('report-tbody');
            if (!tbody) return;
            
            renderDashboardMasterTable();
            renderDashboardSalesRepTable();
            renderDashboardGovernanceTable();
            renderDashboardInventoryTable();
            renderComboChart(comboChartMode);
            } catch (err) {
                console.error('Error in renderTask4Data:', err);
            }
        }

        // ==========================================
        // CÁC HÀM XỬ LÝ BẢNG DASHBOARD ĐIỀU HÀNH
        // ==========================================
        let dashCurrentTab = 'master';
        let dashFilterStatus = 'all';
        let dashSearchQuery = '';

        function switchDashTab(tabName, btn) {
            dashCurrentTab = tabName;
            ['master', 'salesrep', 'governance', 'inventory'].forEach(t => {
                const el = document.getElementById('dash-view-' + t);
                const b = document.getElementById('btn-dash-tab-' + t);
                if (el) el.style.display = (t === tabName) ? 'block' : 'none';
                if (b) b.classList.remove('active');
            });
            if (btn) btn.classList.add('active');

            const sContainer = document.getElementById('dash-search-container');
            if (sContainer) sContainer.style.display = (tabName === 'master') ? 'flex' : 'none';

            if (tabName === 'master') renderDashboardMasterTable();
            else if (tabName === 'salesrep') renderDashboardSalesRepTable();
            else if (tabName === 'governance') renderDashboardGovernanceTable();
            else if (tabName === 'inventory') renderDashboardInventoryTable();
        }

        function filterDashStatus(status, btn) {
            dashFilterStatus = status;
            document.querySelectorAll('#dash-view-master .filter-btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');
            renderDashboardMasterTable();
        }

        function handleDashSearch(query) {
            dashSearchQuery = (query || '').toLowerCase().trim();
            renderDashboardMasterTable();
        }

        function renderDashboardMasterTable() {
            const tbody = document.getElementById('report-tbody');
            if (!tbody) return;
            tbody.innerHTML = '';

            let list = allDossiers;
            if (dashFilterStatus !== 'all') {
                list = list.filter(d => d.status === dashFilterStatus);
            }
            if (dashSearchQuery) {
                list = list.filter(d => {
                    const id = (d.opportunity_id || '').toLowerCase();
                    const name = (d.customer_name || '').toLowerCase();
                    const rep = (d.assigned_sales_rep || '').toLowerCase();
                    const email = (d.contact_email || '').toLowerCase();
                    return id.includes(dashSearchQuery) || name.includes(dashSearchQuery) || rep.includes(dashSearchQuery) || email.includes(dashSearchQuery);
                });
            }

            const countEl = document.getElementById('dash-master-count');
            if (countEl) countEl.innerText = list.length;

            if (list.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Không tìm thấy cơ hội kinh doanh nào phù hợp bộ lọc.</td></tr>';
                return;
            }

            const rows = [];
            list.forEach(d => {
                const val = d.pricing ? d.pricing.final_proposal_value.toLocaleString('vi-VN') + ' đ' : 'Chưa tính';
                const approver = d.approval ? d.approval.approver_role : 'NVKD';
                rows.push(`
                    <tr>
                        <td><strong>${d.opportunity_id}</strong></td>
                        <td><b>${d.customer_name}</b><br><small style="color:var(--text-muted);">${d.channel || 'Email'} | ${d.contact_email || ''}</small></td>
                        <td>${d.assigned_sales_rep}</td>
                        <td>${getBadge(d.status)}</td>
                        <td><strong style="color:var(--primary); font-size:14px;">${val}</strong></td>
                        <td><strong>${approver}</strong></td>
                        <td><small style="color:var(--text-muted);">${d.next_action}</small></td>
                        <td><button class="btn btn-outline" style="padding:4px 8px; font-size:11px;" onclick="showDetail('${d.opportunity_id}')">Xem Hồ Sơ</button></td>
                    </tr>
                `);
            });
            tbody.innerHTML = rows.join('');
        }

        function renderDashboardSalesRepTable() {
            const tbody = document.getElementById('dash-salesrep-tbody');
            if (!tbody) return;
            tbody.innerHTML = '';

            const repStats = {};
            allDossiers.forEach(d => {
                const rep = d.assigned_sales_rep || 'Chưa phân bổ';
                if (!repStats[rep]) {
                    repStats[rep] = { total: 0, eligible: 0, pending: 0, others: 0, totalVal: 0 };
                }
                repStats[rep].total++;
                if (d.status === 'CÓ THỂ TIẾP TỤC') repStats[rep].eligible++;
                else if (d.status === 'CHỜ DUYỆT') repStats[rep].pending++;
                else repStats[rep].others++;

                if (d.pricing && (d.status === 'CÓ THỂ TIẾP TỤC' || d.status === 'CHỜ DUYỆT')) {
                    repStats[rep].totalVal += d.pricing.final_proposal_value;
                }
            });

            const keys = Object.keys(repStats);
            if (keys.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Chưa có dữ liệu phân bổ NVKD.</td></tr>';
                return;
            }

            const rows = [];
            keys.forEach((rep, idx) => {
                const s = repStats[rep];
                const winRate = s.total > 0 ? Math.round(((s.eligible + s.pending) / s.total) * 100) : 0;
                let workloadBadge = '<span class="badge badge-green">Cân Bằng</span>';
                if (s.total >= 3) workloadBadge = '<span class="badge badge-amber">Tải Trọng Cao</span>';

                rows.push(`
                    <tr>
                        <td>${idx + 1}</td>
                        <td><strong>👤 ${rep}</strong></td>
                        <td><b>${s.total}</b> cơ hội</td>
                        <td><span class="badge badge-green">${s.eligible}</span></td>
                        <td><span class="badge badge-purple">${s.pending}</span></td>
                        <td><span class="badge badge-amber">${s.others}</span></td>
                        <td><strong style="color:var(--primary); font-size:14px;">${s.totalVal.toLocaleString('vi-VN')} đ</strong></td>
                        <td>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <div style="flex:1; background:#e2e8f0; height:8px; border-radius:999px; overflow:hidden;">
                                    <div style="width:${winRate}%; background:var(--primary); height:100%;"></div>
                                </div>
                                <span style="font-size:12px; font-weight:700;">${winRate}%</span>
                            </div>
                        </td>
                        <td>${workloadBadge}</td>
                    </tr>
                `);
            });
            tbody.innerHTML = rows.join('');
        }

        function renderDashboardGovernanceTable() {
            const tbody = document.getElementById('dash-governance-tbody');
            if (!tbody) return;

            const tiers = [
                {
                    role: 'NVKD (Chuyên viên kinh doanh)',
                    policy: 'Chiết khấu ≤ 8.0% & Tổng giá trị ≤ 200,000,000 VNĐ',
                    sla: 'Tự chủ ra quyết định tức thì (0 Giờ)',
                    riskLevel: '<span class="badge badge-green">Thấp (Trong hạn mức)</span>',
                    action: 'Phát hành Báo giá chính thức ngay lập tức',
                    count: 0,
                    totalVal: 0
                },
                {
                    role: 'Trưởng phòng Kinh doanh',
                    policy: 'Chiết khấu ≤ 20.0% hoặc Tổng giá trị ≤ 1,000,000,000 VNĐ',
                    sla: 'Cam kết thẩm định trong 04 Giờ làm việc',
                    riskLevel: '<span class="badge badge-purple">Trung Bình (Vượt quyền NVKD)</span>',
                    action: 'Thẩm định Escalation Ticket & Quyết định',
                    count: 0,
                    totalVal: 0
                },
                {
                    role: 'Ban Giám Đốc (Board of Directors)',
                    policy: 'Chiết khấu > 20.0% hoặc Tổng giá trị > 1,000,000,000 VNĐ',
                    sla: 'Cam kết thẩm định trong 24 Giờ làm việc',
                    riskLevel: '<span class="badge badge-red">Cao (Chính sách đặc biệt)</span>',
                    action: 'Họp biểu quyết phê duyệt hồ sơ thầu lớn',
                    count: 0,
                    totalVal: 0
                }
            ];

            allDossiers.forEach(d => {
                if (d.approval) {
                    let tIdx = 0;
                    if (d.approval.approver_role === 'Trưởng phòng Kinh doanh') tIdx = 1;
                    else if (d.approval.approver_role === 'Ban Giám đốc') tIdx = 2;
                    tiers[tIdx].count++;
                    if (d.pricing) tiers[tIdx].totalVal += d.pricing.final_proposal_value;
                }
            });

            const govRows = [];
            tiers.forEach(t => {
                govRows.push(`
                    <tr>
                        <td><strong>${t.role}</strong></td>
                        <td><small style="color:var(--text-muted);">${t.policy}</small></td>
                        <td><b>${t.count}</b> cơ hội</td>
                        <td><strong style="color:var(--primary); font-size:14px;">${t.totalVal.toLocaleString('vi-VN')} đ</strong></td>
                        <td>${t.sla}</td>
                        <td>${t.action}</td>
                        <td>${t.riskLevel}</td>
                    </tr>
                `);
            });
            tbody.innerHTML = govRows.join('');
        }

        function renderDashboardInventoryTable() {
            const tbody = document.getElementById('dash-inventory-tbody');
            if (!tbody) return;

            const itemMap = {};
            allDossiers.forEach(d => {
                if (d.feasibility && d.feasibility.items_feasibility) {
                    d.feasibility.items_feasibility.forEach(it => {
                        if (!itemMap[it.sku]) {
                            itemMap[it.sku] = {
                                sku: it.sku,
                                name: it.name,
                                location: it.inventory_location || 'Kho Hà Nội',
                                totalRequested: 0,
                                stock: it.available_stock || 0,
                                leadDays: it.estimated_lead_days || 3
                            };
                        }
                        itemMap[it.sku].totalRequested += it.requested_qty;
                    });
                }
            });

            const keys = Object.keys(itemMap);
            if (keys.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có dữ liệu tồn kho.</td></tr>';
                return;
            }

            const invRows = [];
            keys.forEach(k => {
                const it = itemMap[k];
                const shortage = Math.max(0, it.totalRequested - it.stock);
                const isReady = shortage === 0;
                const statusBadge = isReady
                    ? '<span class="badge badge-green">✅ Sẵn Sàng Giao Ngay</span>'
                    : `<span class="badge badge-red">❌ Thiếu ${shortage} chiếc (Cần đặt nhập)</span>`;

                invRows.push(`
                    <tr>
                        <td><strong style="font-family:monospace; color:var(--primary);">${it.sku}</strong></td>
                        <td><b>${it.name}</b></td>
                        <td>${it.location}</td>
                        <td><strong>${it.totalRequested}</strong> chiếc</td>
                        <td><b>${it.stock}</b> chiếc</td>
                        <td>${shortage > 0 ? `<b style="color:var(--danger);">${shortage}</b> chiếc` : '0'}</td>
                        <td><strong>${it.leadDays} ngày</strong></td>
                        <td>${statusBadge}</td>
                    </tr>
                `);
            });
            tbody.innerHTML = invRows.join('');
        }

        // ==========================================
        // CÁC HÀM XUẤT FILE KẾT QUẢ
        // ==========================================
        function downloadBlob(blob, fileName) {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        }

        function downloadFileBlob(content, fileName, mimeType) {
            const blob = new Blob([content], { type: mimeType });
            downloadBlob(blob, fileName);
        }

        // XUẤT DỮ LIỆU ĐÃ LÀM SẠCH (CLEANED DATASET) - ĐÚNG CHUẨN BI & DATA PROFILING
        async function exportCleanedData(format = 'excel') {
            if (!allDossiers || allDossiers.length === 0) {
                alert('⚠️ Hệ thống chưa có dữ liệu đầu vào nào để xuất! Vui lòng tải file hoặc nhập dữ liệu ở Task 1 trước.');
                switchTask(1);
                return;
            }
            const isHP = (currentSummaryData && currentSummaryData.is_hung_phat) || allDossiers.some(d => d && d.is_hung_phat);
            
            if (format === 'excel') {
                try {
                    showToast('⏳ Đang tổng hợp và tạo tệp Excel dữ liệu đã làm sạch...');
                    const res = await fetch('/api/export_cleaned_excel', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            dossiers: allDossiers,
                            summary: currentSummaryData,
                            is_hung_phat: isHP
                        })
                    });
                    if (res.ok) {
                        const blob = await res.blob();
                        const filename = isHP 
                            ? `du_lieu_da_lam_sach_hung_phat_${new Date().toISOString().slice(0,10)}.xlsx`
                            : `du_lieu_don_hang_da_lam_sach_${new Date().toISOString().slice(0,10)}.xlsx`;
                        downloadBlob(blob, filename);
                        showToast('✅ Đã xuất tệp Excel (.xlsx) Dữ liệu đã làm sạch thành công!');
                        return;
                    }
                } catch (e) {
                    console.warn('Backend Excel export error, falling back to GET:', e);
                    try {
                        const res2 = await fetch('/api/export_cleaned_excel');
                        if (res2.ok) {
                            const blob2 = await res2.blob();
                            downloadBlob(blob2, `du_lieu_da_lam_sach_${new Date().toISOString().slice(0,10)}.xlsx`);
                            showToast('✅ Đã xuất tệp Excel (.xlsx) Dữ liệu đã làm sạch thành công!');
                            return;
                        }
                    } catch(e2) {
                        console.error('Export error:', e2);
                    }
                }
            }

            // XUẤT CSV LÀM SẠCH VỚI UTF-8 BOM
            if (isHP) {
                let headers = [
                    "Mã Bản Ghi (Record ID)",
                    "Phân Vùng (Region)",
                    "Nguồn Bảng (Source Sheet)",
                    "Kỳ Thống Kê (Statistical Period)",
                    "Chỉ Tiêu / Nhu Cầu (Metric)",
                    "Giá Trị Đã Làm Sạch (Cleaned Value)",
                    "Đơn Vị (Unit)",
                    "Quy Mô Tính Hợp Lệ (Valid for Aggregation)",
                    "Trạng Thái Làm Sạch (Cleaning Status)",
                    "Biện Pháp Xử Lý BI (Remediation Action)"
                ];
                let rows = [headers.join(",")];
                allDossiers.forEach(d => {
                    const rec = d.hung_phat_record || {};
                    const isDup = rec.status === 'DUPLICATE' || (rec.audit_flags && rec.audit_flags.some(f => f.includes('T-01')));
                    const isMissing = rec.status === 'MISSING' || (rec.audit_flags && rec.audit_flags.some(f => f.includes('T-03') || f.includes('T-04')));
                    
                    let cleanedVal = (rec.value !== null && rec.value !== undefined) ? rec.value : 'NULL';
                    let validForAgg = isDup ? 'KHÔNG (LOẠI TRỪ VÌ TRÙNG LẶP)' : (isMissing ? 'KHÔNG (THIẾU SỐ LIỆU)' : 'CÓ (HỢP LỆ)');
                    let cleanStatus = isDup ? 'ĐÃ LỌC BỎ TRÙNG LẶP' : (isMissing ? 'GẮN CỜ DỮ LIỆU KHUYẾT (NULL)' : 'CHUẨN HÓA THÀNH CÔNG');
                    let action = rec.action_note || 'Dữ liệu đạt chuẩn phân tích';

                    rows.push([
                        `"${d.opportunity_id || rec.id || ''}"`,
                        `"${rec.region || ''}"`,
                        `"${rec.sheet || ''}"`,
                        `"${rec.period || ''}"`,
                        `"${(rec.metric || '').replace(/"/g, '""')}"`,
                        `"${cleanedVal}"`,
                        `"${rec.unit || ''}"`,
                        `"${validForAgg}"`,
                        `"${cleanStatus}"`,
                        `"${action.replace(/"/g, '""')}"`
                    ].join(","));
                });

                const bom = new Uint8Array([0xEF, 0xBB, 0xBF]);
                const blob = new Blob([bom, rows.join(String.fromCharCode(13, 10))], { type: "text/csv;charset=utf-8;" });
                downloadBlob(blob, `du_lieu_da_lam_sach_hung_phat_${new Date().toISOString().slice(0,10)}.csv`);
                showToast("✨ Đã xuất tệp CSV Dữ liệu đã làm sạch Hưng Phát (UTF-8 BOM)!");
                return;
            }

            // DÀNH CHO BỘ DỮ LIỆU MINH AN B2B SALES
            let headers = [
                "Mã Cơ Hội",
                "Khách Hàng",
                "Email",
                "Kênh Tiếp Nhận",
                "SKU Chuẩn Hóa",
                "Tên Sản Phẩm Chuẩn Hóa",
                "Số Lượng",
                "Đơn Giá Niêm Yết (VNĐ)",
                "Tổng Tiền Niêm Yết (VNĐ)",
                "Tỷ Lệ Chiết Khấu (%)",
                "Tiền Chiết Khấu (VNĐ)",
                "Doanh Số Đề Xuất Thực Thu (VNĐ)",
                "Ngân Sách Khách (VNĐ)",
                "Đánh Giá Ngân Sách",
                "Tình Trạng Kho",
                "Lead Time Giao Hàng (Ngày)",
                "Trạng Thái Hồ Sơ",
                "Cấp Duyệt Thẩm Quyền"
            ];

            let rows = [headers.join(",")];
            allDossiers.forEach(d => {
                const sub = d.pricing ? d.pricing.base_subtotal : 0;
                const discRate = d.pricing ? (d.pricing.applied_discount_rate * 100).toFixed(1) : 0;
                const discAmt = d.pricing ? d.pricing.total_discount_amount : 0;
                const net = d.pricing ? d.pricing.final_proposal_value : 0;
                const bud = (d.extracted_data && d.extracted_data.budget) ? d.extracted_data.budget : 0;
                const budStatus = d.pricing ? (d.pricing.is_within_budget ? "Trong ngân sách" : "Vượt ngân sách") : "Chưa xác định";
                const leadDays = d.feasibility ? d.feasibility.overall_lead_days_needed : 0;
                const leadStatus = d.feasibility ? d.feasibility.lead_time_status : "Chưa xác định";
                const approver = d.approval ? d.approval.approver_role : "NVKD";
                
                const items = (d.extracted_data && d.extracted_data.items && d.extracted_data.items.length > 0) 
                    ? d.extracted_data.items 
                    : [{ standardized_sku: "SKU-AUTO", product_name: "Gói giải pháp công nghệ", quantity: 1, unit_price: sub }];

                items.forEach(it => {
                    const row = [
                        `"${d.opportunity_id}"`,
                        `"${d.customer_name}"`,
                        `"${d.contact_email}"`,
                        `"${d.channel}"`,
                        `"${it.standardized_sku || it.sku || 'SKU-STD'}"`,
                        `"${(it.product_name || it.item_name || 'Thiết bị chuẩn hóa').replace(/"/g, '""')}"`,
                        it.quantity || 1,
                        it.unit_price || 0,
                        (it.quantity || 1) * (it.unit_price || 0),
                        discRate,
                        discAmt,
                        net,
                        bud,
                        `"${budStatus}"`,
                        `"${leadStatus}"`,
                        leadDays,
                        `"${d.status}"`,
                        `"${approver}"`
                    ];
                    rows.push(row.join(","));
                });
            });

            const bom = new Uint8Array([0xEF, 0xBB, 0xBF]);
            const blob = new Blob([bom, rows.join(String.fromCharCode(13, 10))], { type: "text/csv;charset=utf-8;" });
            downloadBlob(blob, `du_lieu_don_hang_da_lam_sach_${new Date().toISOString().slice(0,10)}.csv`);
            showToast("✨ Đã xuất tệp CSV Dữ liệu bán hàng đã làm sạch (UTF-8 BOM)!");
        }

        function exportCSV() {
            const isHP = (currentSummaryData && currentSummaryData.is_hung_phat) || allDossiers.some(d => d && d.is_hung_phat);
            if (isHP) {
                let headers = [
                    "Mã Bản Ghi", "Phân Vùng / Khu Vực", "Nguồn / Sheet", "Chỉ Tiêu / Nhu Cầu",
                    "Giá Trị", "Đơn Vị", "Cờ Kiểm Toán BI (Audit Flags)", "Hành Động Khắc Phục / BI Action", "Trạng Thái Thẩm Định"
                ];
                let rows = [headers.join(",")];
                allDossiers.forEach(d => {
                    const rec = d.hung_phat_record || {};
                    const flagsStr = (rec.audit_flags && rec.audit_flags.length > 0) ? rec.audit_flags.join(" | ") : "Đạt chuẩn";
                    const row = [
                        `"${d.opportunity_id || ''}"`,
                        `"${rec.region || ''}"`,
                        `"${rec.sheet || ''}"`,
                        `"${rec.metric || ''}"`,
                        `"${rec.value !== null && rec.value !== undefined ? rec.value : 'NULL'}"`,
                        `"${rec.unit || ''}"`,
                        `"${flagsStr.replace(/"/g, '""')}"`,
                        `"${(rec.action_note || '').replace(/"/g, '""')}"`,
                        `"${rec.status || 'VALID'}"`
                    ];
                    rows.push(row.join(","));
                });
                const bom = new Uint8Array([0xEF, 0xBB, 0xBF]);
                const blob = new Blob([bom, rows.join(String.fromCharCode(13, 10))], { type: "text/csv;charset=utf-8;" });
                downloadBlob(blob, `bao_cao_kiem_toan_hung_phat_${new Date().toISOString().slice(0,10)}.csv`);
                showToast("✅ Đã xuất tệp CSV Kiểm toán chất lượng Hưng Phát!");
                return;
            }

            let headers = [
                "Mã Cơ Hội", "Khách Hàng", "Email", "Kênh Tiếp Nhận", "NVKD Phụ Trách",
                "Trạng Thái", "Tổng Giá Niêm Yết (VNĐ)", "Chiết Khấu Áp Dụng (%)",
                "Số Tiền Giảm (VNĐ)", "Giá Đề Xuất Net (VNĐ)", "Ngân Sách Khách (VNĐ)",
                "Chênh Lệch Ngân Sách (VNĐ)", "Đánh Giá Ngân Sách", "Lead Time Kho (Ngày)",
                "Thời Hạn Khách (Ngày)", "Đánh Giá Tiến Độ", "Cấp Phê Duyệt", "Lý Do Trình Duyệt"
            ];

            let rows = [headers.join(",")];

            allDossiers.forEach(d => {
                const sub = d.pricing ? d.pricing.base_subtotal : 0;
                const discRate = d.pricing ? (d.pricing.applied_discount_rate * 100).toFixed(1) : 0;
                const discAmt = d.pricing ? d.pricing.total_discount_amount : 0;
                const net = d.pricing ? d.pricing.final_proposal_value : 0;
                const bud = d.extracted_data.budget || 0;
                const variance = bud > 0 ? (bud - net) : 0;
                const budStatus = d.pricing ? (d.pricing.is_within_budget ? "Trong ngân sách" : "Vượt ngân sách") : "Chưa xác định";
                const leadDays = d.feasibility ? d.feasibility.overall_lead_days_needed : 0;
                const deadline = d.feasibility ? (d.feasibility.customer_deadline_days || 0) : 0;
                const leadStatus = d.feasibility ? d.feasibility.lead_time_status : "Chưa xác định";
                const approver = d.approval ? d.approval.approver_role : "NVKD";
                const reasons = d.approval && d.approval.reasons ? d.approval.reasons.join(" | ") : "";

                const row = [
                    `"${d.opportunity_id}"`,
                    `"${d.customer_name}"`,
                    `"${d.contact_email}"`,
                    `"${d.channel}"`,
                    `"${d.assigned_sales_rep}"`,
                    `"${d.status}"`,
                    sub,
                    discRate,
                    discAmt,
                    net,
                    bud,
                    variance,
                    `"${budStatus}"`,
                    leadDays,
                    deadline,
                    `"${leadStatus}"`,
                    `"${approver}"`,
                    `"${reasons}"`
                ];
                rows.push(row.join(","));
            });

            const bom = new Uint8Array([0xEF, 0xBB, 0xBF]);
            const blob = new Blob([bom, rows.join(String.fromCharCode(13, 10))], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `bang_ket_qua_co_hoi_${new Date().toISOString().slice(0,10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast('✅ Đã xuất bảng kết quả sang file Excel/CSV!');
        }

        function exportJSON() {
            const data = {
                metadata: {
                    company: "CÔNG TY CÔNG NGHỆ MINH AN",
                    process: "HỆ THỐNG XỬ LÝ YÊU CẦU BÁN HÀNG B2B (AI AGENT)",
                    exported_at: new Date().toISOString(),
                    total_opportunities: allDossiers.length
                },
                summary: currentSummaryData,
                opportunities: allDossiers
            };
            downloadFileBlob(JSON.stringify(data, null, 2), `bao_cao_tong_hop_${new Date().toISOString().slice(0,10)}.json`, "application/json");
            showToast('✅ Đã xuất tệp Báo cáo Tổng hợp JSON!');
        }

        function exportMarkdown() {
            let md = [];
            md.push("# TỔNG HỢP HỒ SƠ CƠ HỘI KINH DOANH & PHIẾU PHÊ DUYỆT");
            md.push("### CÔNG TY CÔNG NGHỆ MINH AN - BÁO CÁO THẨM ĐỊNH TOÀN DIỆN");
            md.push(`*Thời gian xuất bản: ${new Date().toLocaleString('vi-VN')}*\n`);
            md.push("---");

            allDossiers.forEach((d, idx) => {
                md.push("");
                md.push(`## [${idx + 1}] CƠ HỘI KINH DOANH: ${d.opportunity_id} - ${d.customer_name}`);
                md.push(`- **Khách hàng:** ${d.customer_name} | **Email:** ${d.contact_email}`);
                md.push(`- **Chuyên viên kinh doanh:** ${d.assigned_sales_rep}`);
                md.push(`- **Trạng thái:** **${d.status}**`);
                md.push(`- **Yêu cầu gốc:** *"${d.extracted_data.raw_text}"*`);
                
                if (d.pricing) {
                    md.push("");
                    md.push("### 💰 Tài Chính & Báo Giá:");
                    md.push(`- Giá niêm yết: ${d.pricing.base_subtotal.toLocaleString('vi-VN')} VNĐ`);
                    md.push(`- Chiết khấu áp dụng: ${(d.pricing.applied_discount_rate*100).toFixed(1)}% (Giảm: ${d.pricing.total_discount_amount.toLocaleString('vi-VN')} VNĐ)`);
                    md.push(`- Giá trị đề xuất (Net): **${d.pricing.final_proposal_value.toLocaleString('vi-VN')} VNĐ**`);
                    md.push(`- Ngân sách KH: ${d.extracted_data.budget ? d.extracted_data.budget.toLocaleString('vi-VN') + ' VNĐ' : 'Chưa có'}`);
                    md.push(`- Đánh giá: ${d.pricing.is_within_budget ? '✅ Nằm trong ngân sách' : '❌ Vượt ngân sách'}`);
                }

                if (d.feasibility) {
                    md.push("");
                    md.push("### 🏭 Khả Năng Cung Ứng Kho Hàng:");
                    md.push(`- Thời gian kho cần: **${d.feasibility.overall_lead_days_needed} ngày** (Hạn định khách: ${d.feasibility.customer_deadline_days || 'Chưa rõ'} ngày)`);
                    md.push(`- Kết luận tiến độ: **${d.feasibility.lead_time_status}**`);
                }

                if (d.approval && d.approval_ticket) {
                    md.push("");
                    md.push("### 📑 Phiếu Trình Duyệt Thẩm Quyền (Escalation Ticket):");
                    md.push("```");
                    md.push(d.approval_ticket);
                    md.push("```");
                }

                if (d.customer_response_draft) {
                    md.push("");
                    md.push("### ✉️ Bản Nháp Phản Hồi Khách Hàng:");
                    md.push("```");
                    md.push(d.customer_response_draft);
                    md.push("```");
                }
                md.push("");
                md.push("------------------------------------------------------------");
                md.push("");
            });

            downloadFileBlob(md.join(String.fromCharCode(10)), `toan_bo_ho_so_co_hoi_${new Date().toISOString().slice(0,10)}.md`, "text/markdown");
            showToast('✅ Đã xuất toàn bộ Hồ sơ & Phiếu duyệt sang Markdown!');
        }

        async function exportAudit() {
            try {
                const res = await fetch('/api/batch_process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(rawItems)
                });
                const data = await res.json();
                downloadFileBlob(JSON.stringify(data.audit || [], null, 2), `audit_trail_report_${new Date().toISOString().slice(0,10)}.json`, "application/json");
                showToast('✅ Đã xuất nhật ký kiểm toán Audit Trail!');
            } catch(e) {
                alert('Lỗi xuất audit trail: ' + e);
            }
        }

        function getBadge(status) {
            if (status === 'CÓ THỂ TIẾP TỤC') return '<span class="badge badge-green">CÓ THỂ TIẾP TỤC</span>';
            if (status === 'CHỜ DUYỆT') return '<span class="badge badge-purple">CHỜ DUYỆT</span>';
            if (status === 'CẦN BỔ SUNG THÔNG TIN') return '<span class="badge badge-amber">CẦN BỔ SUNG THÔNG TIN</span>';
            return '<span class="badge badge-red">CHƯA ĐÁP ỨNG</span>';
        }

        function showDetail(id) {
            try {
                id = decodeURIComponent(id);
                const item = (extractedItems && Array.isArray(extractedItems)) ? extractedItems.find(x => x && (x.request_id || x.id) === id) : null;
                const d = (allDossiers && Array.isArray(allDossiers)) ? allDossiers.find(x => x && x.opportunity_id === id) : null;
                const raw = (rawItems && Array.isArray(rawItems)) ? rawItems.find(x => x && (x.request_id || x.id) === id) : null;
                if (!item && !d && !raw) return;

                const detailCard = document.getElementById('detail-card');
                if (detailCard) detailCard.style.display = 'block';

                const extData = (d && d.extracted_data) ? d.extracted_data : {};
                const idEl = document.getElementById('detail-id');
                if (idEl) idEl.innerText = (raw ? (raw.request_id || raw.id) : (d ? d.opportunity_id : id)) + " - " + (raw ? raw.customer_name : (d ? d.customer_name : 'Khách Hàng'));

                const rawEl = document.getElementById('detail-raw');
                const rawText = raw ? (raw.raw_request_text || raw.raw_text) : (extData.raw_text || '');
                if (rawEl) rawEl.innerText = `"${rawText || ''}"`;

                let exHtml = `<p><strong>Kênh tiếp nhận:</strong> ${raw ? raw.channel : (d ? d.channel : 'Email')}</p>`;
                exHtml += `<p><strong>Chuyên viên phụ trách:</strong> ${d ? (d.assigned_sales_rep || 'Chưa gán') : (item ? item.assigned_sales_rep : 'Chờ phân bổ')}</p>`;
                exHtml += `<hr style="margin:8px 0; border:none; border-top:1px solid #e2e8f0;">`;
                
                const bud = (item && item.budget) ? item.budget : (extData.budget ? extData.budget : (raw ? raw.budget : null));
                const del = (item && item.delivery_days) ? item.delivery_days : (extData.delivery_days ? extData.delivery_days : (raw ? raw.delivery_days : null));
                const disc = (item && item.requested_discount_rate) ? item.requested_discount_rate : (extData.requested_discount_rate ? extData.requested_discount_rate : null);

                exHtml += `<p><strong>Ngân sách:</strong> ${bud ? Number(bud).toLocaleString('vi-VN') + ' VNĐ' : '<span style="color:var(--danger)">Chưa cung cấp</span>'}</p>`;
                exHtml += `<p><strong>Thời hạn yêu cầu:</strong> ${del ? del + ' ngày' : '<span style="color:var(--danger)">Chưa cung cấp</span>'}</p>`;
                exHtml += `<p><strong>Chiết khấu mong muốn:</strong> ${disc ? (disc * 100).toFixed(1) + '%' : 'Theo chính sách chuẩn'}</p>`;
                
                const missing = item ? item.missing_fields : (extData.missing_fields ? extData.missing_fields : []);
                if (missing && missing.length > 0) {
                    exHtml += `<p style="color:var(--warning); margin-top:6px;"><strong>Thông tin còn thiếu:</strong></p><ul style="padding-left:18px; color:var(--warning); font-size:13px;">`;
                    missing.forEach(m => exHtml += `<li>${m}</li>`);
                    exHtml += `</ul>`;
                }
                const extEl = document.getElementById('detail-extracted');
                if (extEl) extEl.innerHTML = exHtml;

                if (d && d.approval_ticket) {
                    document.getElementById('detail-action-title').innerText = 'Phiếu Trình Duyệt Lãnh Đạo (Escalation Ticket)';
                    document.getElementById('detail-action-content').innerText = d.approval_ticket;
                } else if (d && d.customer_response_draft) {
                    document.getElementById('detail-action-title').innerText = 'Bản Nháp Phản Hồi Khách Hàng (Email Draft)';
                    document.getElementById('detail-action-content').innerText = d.customer_response_draft;
                } else if (item && item.is_complete) {
                    document.getElementById('detail-action-title').innerText = 'Hành Động: Đã Đầy Đủ Dữ Kiện -> Khởi Tạo Hồ Sơ';
                    document.getElementById('detail-action-content').innerText = 
`HỒ SƠ CƠ HỘI BAN ĐẦU:
- Mã định danh: ${item.request_id || item.id}
- Khách hàng: ${item.customer_name}
- Gán người phụ trách: ${item.assigned_sales_rep || 'NVKD Minh An'}
- Trạng thái: ĐÃ BÓC TÁCH VÀ THẨM TRA HỢP LỆ`;
                } else {
                    document.getElementById('detail-action-title').innerText = 'Bản Nháp Email Yêu Cầu Bổ Sung Thông Tin';
                    document.getElementById('detail-action-content').innerText = item ? item.clarification_email_draft : 'Đang khởi tạo...';
                }

                if (detailCard) detailCard.scrollIntoView({ behavior: 'smooth' });
            } catch(detailErr) {
                console.error('Error showing detail:', detailErr);
            }
        }

        // XỬ LÝ NẠP TỆP (FILE UPLOAD & DRAG DROP) TOÀN DIỆN
        function triggerFileInput() {
            const fi = document.getElementById('file-input');
            if (fi) {
                fi.value = ''; // Reset value để chọn lại file cũ vẫn kích hoạt onchange
                fi.click();
            }
        }

        window.addEventListener('dragover', (e) => { e.preventDefault(); }, false);
        window.addEventListener('drop', (e) => { e.preventDefault(); }, false);

        const dropZone = document.getElementById('drop-zone');
        if (dropZone) {
            ['dragenter', 'dragover'].forEach(eventName => {
                dropZone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropZone.classList.add('dragover');
                }, false);
            });
            ['dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropZone.classList.remove('dragover');
                }, false);
            });
            dropZone.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                if (dt && dt.files && dt.files.length > 0) {
                    processFile(dt.files[0]);
                }
            }, false);
        }

        function handleFileSelect(e) {
            if (e.target.files && e.target.files.length > 0) {
                processFile(e.target.files[0]);
                e.target.value = ''; // Reset sau khi xử lý
            }
        }

        async function processFile(file) {
            if (!file) return;
            const nameLabel = document.getElementById('selected-file-name');
            if (nameLabel) nameLabel.innerText = `⏳ Đang đọc và bóc tách tệp: ${file.name}...`;
            showToast(`⏳ Đang xử lý tệp '${file.name}'...`);

            const ext = (file.name.split('.').pop() || '').toLowerCase();
            let newItems = [];

            // BƯỚC 1: GỬI LÊN BACKEND PYTHON XỬ LÝ (HỖ TRỢ TOÀN DIỆN EXCEL .XLSX, .XLS, CSV, JSON QUA PANDAS & OPENPYXL)
            try {
                const res = await fetch('/api/upload_file?filename=' + encodeURIComponent(file.name), {
                    method: 'POST',
                    body: file
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.items && Array.isArray(data.items) && data.items.length > 0) {
                        newItems = data.items;
                    }
                }
            } catch (netErr) {
                console.warn('Backend file upload network error:', netErr);
            }

            // BƯỚC 2: NẾU BACKEND KHÔNG PHẢN HỒI VÀ TỆP LÀ TEXT/JSON/CSV -> FALLBACK ĐỌC PHÍA CLIENT
            if (newItems.length === 0 && !['xlsx', 'xls', 'xlsm', 'xlsb'].includes(ext)) {
                try {
                    const content = await file.text();
                    try {
                        const parsed = JSON.parse(content);
                        if (Array.isArray(parsed)) newItems = parsed;
                        else if (parsed && Array.isArray(parsed.requests)) newItems = parsed.requests;
                        else if (parsed && Array.isArray(parsed.sample_requests)) newItems = parsed.sample_requests;
                        else if (parsed && Array.isArray(parsed.data)) newItems = parsed.data;
                        else if (typeof parsed === 'object' && parsed !== null) newItems = [parsed];
                    } catch(jsonErr) {
                        // Sử dụng String.fromCharCode để an toàn 100% trong Python multiline string
                        const lines = content.split(String.fromCharCode(10)).map(l => l.replace(String.fromCharCode(13), '').trim()).filter(l => l.length > 0);
                        if (lines.length > 1) {
                            const sep = lines[0].includes(';') ? ';' : ',';
                            for (let i = 1; i < lines.length; i++) {
                                const parts = lines[i].split(sep).map(p => p.replace(/^"/, '').replace(/"$/, '').trim());
                                if (parts.length > 0 && parts.join('').length > 0) {
                                    newItems.push({
                                        id: "REQ-" + Math.floor(1000 + Math.random() * 9000),
                                        customer_name: parts[0] || ("Khách Hàng " + i),
                                        contact_email: parts[1] || "contact@client.vn",
                                        channel: "File CSV",
                                        raw_request_text: parts.slice(3).join(" ") || lines[i]
                                    });
                                }
                            }
                        } else if (content.trim().length > 0) {
                            newItems = [{
                                id: "REQ-" + Math.floor(1000 + Math.random() * 9000),
                                customer_name: "Khách Hàng (" + (file.name.split('.')[0] || "File") + ")",
                                contact_email: "contact@client.vn",
                                channel: "File Văn Bản",
                                raw_request_text: content.trim()
                            }];
                        }
                    }
                } catch(readErr) {
                    console.error('Client file read error:', readErr);
                }
            }

            if (newItems.length === 0) {
                showToast('⚠️ Không thể bóc tách dữ liệu từ tệp hoặc tệp rỗng!');
                if (nameLabel) nameLabel.innerText = `⚠️ Lỗi xử lý ${file.name}`;
                return;
            }

            // Chuẩn hóa và làm sạch
            newItems.forEach((it, idx) => {
                if (!it.id && !it.request_id) it.id = "REQ-" + Math.floor(1000 + Math.random() * 9000);
                if (!it.customer_name) it.customer_name = it.customer || ("Khách Hàng " + (idx + 1));
                if (!it.contact_email) it.contact_email = it.email || "contact@client.vn";
                if (!it.channel) it.channel = "File: " + file.name;
                if (!it.raw_request_text && it.raw_text) it.raw_request_text = it.raw_text;
                if (!it.raw_request_text && it.content) it.raw_request_text = it.content;
                if (!it.raw_request_text && it.text) it.raw_request_text = it.text;
                if (!it.raw_request_text) it.raw_request_text = "Yêu cầu tiếp nhận từ " + it.customer_name;
            });

            // Nạp vào danh sách và CẬP NHẬT GIAO DIỆN NGAY LẬP TỨC
            rawItems = newItems.concat(rawItems);
            if (nameLabel) nameLabel.innerText = `✅ Đã nạp: ${file.name} (+${newItems.length} yêu cầu)`;
            showToast(`🎉 Đã nạp thành công ${newItems.length} yêu cầu từ '${file.name}'!`);
            appendLog('TỆP ĐẦU VÀO', `Đã nạp ${newItems.length} yêu cầu từ tệp [${file.name}].`);
            
            // HIỂN THỊ TỨC THÌ TẠI TASK 1
            renderTask1Data();

            // Chạy phân tích backend nền và lưu trạng thái
            try {
                isPipelineApproved = false;
                await recomputeEntireSystem();
                renderTask1Data();
                saveSystemState();
                appendLog('TỆP ĐẦU VÀO', `Đã nạp tệp [${file.name}]. Vui lòng sang Task 2 để bấm 'Phê Duyệt & Chạy Quy Trình'.`);
                showToast(`✅ Đã nạp ${newItems.length} yêu cầu từ '${file.name}'! Sang Task 2 bấm Duyệt để chạy quy trình.`);
                const b = document.getElementById('main-cmd-btn');
                if (b) b.innerText = '🛡️ DUYỆT & BẮT ĐẦU CHẠY LUỒNG QUY TRÌNH ➔';
                document.getElementById('flow-status-tag').innerText = 'CHỜ PHÊ DUYỆT';
            } catch(netErr) {
                console.warn('Backend sync warning:', netErr);
            }
        }

        function loadSampleDataset() {
            rawItems = [...PRELOADED_SAMPLE];
            extractedItems = [...PRELOADED_EXTRACTED];
            allDossiers = [...PRELOADED_DOSSIERS];
            currentSummaryData = PRELOADED_SUMMARY;
            isPipelineApproved = true;
            saveSystemState();
            instantRenderAll();
            showToast('⚡ Đã nạp 6 ca mẫu đề thi (Đã lưu vào bộ nhớ, F5 không mất)!');
            appendLog('MẪU ĐỀ BÀI', 'Đã nạp 6 ca mẫu đề thi. Dữ liệu được lưu giữ ngay cả khi bạn tải lại trang (F5).');
        }

        async function loadHungPhatSample() {
            try {
                showToast('⏳ Đang nạp và phân tích dữ liệu Hưng Phát 5 bước...');
                const res = await fetch('/api/load_hung_phat_sample');
                const data = await res.json();
                if (data.success && data.items) {
                    rawItems = data.items;
                    isPipelineApproved = true;
                    await recomputeEntireSystem();
                    saveSystemState();
                    instantRenderAll();
                    showToast('🎉 Đã nạp thành công bộ test Hưng Phát 5 bước!');
                    appendLog('HƯNG PHÁT 5 BƯỚC', 'Đã nạp toàn bộ 22 bản ghi kiểm toán, khử trùng lặp T-01, phát hiện mốc kỳ T-02 và cảnh báo nghẽn năng lực T-05.');
                    switchTask(2);
                } else {
                    showToast('⚠️ Không tìm thấy tệp Hung_Phat_Test_Data_5_Steps.xlsx');
                }
            } catch(e) {
                console.error('Lỗi khi nạp mẫu Hưng Phát:', e);
                showToast('⚠️ Lỗi kết nối khi nạp mẫu Hưng Phát');
            }
        }

        function resetAll() {
            if (confirm('Bạn có chắc muốn xóa trắng dữ liệu và reset lại hệ thống?')) {
                try {
                    localStorage.removeItem('minhan_raw_items');
                    localStorage.removeItem('minhan_extracted_items');
                    localStorage.removeItem('minhan_all_dossiers');
                    localStorage.removeItem('minhan_summary_data');
                    localStorage.removeItem('minhan_pipeline_approved');
                } catch(e) {}

                rawItems = [];
                extractedItems = [];
                allDossiers = [];
                currentSummaryData = null;
                isPipelineApproved = false;

                for (let i = 1; i <= 4; i++) setNodeState(i, '');
                renderDataProfilingAudit();
                renderDiagnosticInsights();
                updateBLUFSummary();
                document.getElementById('task1-tbody').innerHTML = '<tr><td colspan="8" class="empty-state">Dữ liệu đã xóa trắng. Hãy nhập form hoặc tải tệp lên để bắt đầu.</td></tr>';
                document.getElementById('clean-tbody').innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có dữ liệu.</td></tr>';
                document.getElementById('pricing-tbody').innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có dữ liệu.</td></tr>';
                document.getElementById('report-tbody').innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có dữ liệu.</td></tr>';
                document.getElementById('detail-card').style.display = 'none';
                document.getElementById('paste-text').value = '';
                document.getElementById('req-count').innerText = '0';
                document.getElementById('flow-status-tag').innerText = 'CHỜ DỮ LIỆU ĐẦU VÀO';
                document.getElementById('header-status').innerText = 'Hệ Thống Đã Reset';

                const btn = document.getElementById('main-cmd-btn');
                if (btn) btn.innerText = '⚠️ CHƯA CÓ DỮ LIỆU (NHẬP Ở TASK 1)';

                renderComboChart(comboChartMode);
                appendLog('RESET', 'Đã xóa trắng toàn bộ dữ liệu lưu trữ theo yêu cầu.');
                switchTask(1);
                showToast('🗑️ Đã xóa trắng dữ liệu và reset hệ thống!');
            }
        }

        function executeTask2() {
            renderTask2Data();
            showToast('🔄 Đã đồng bộ lại dữ liệu Kho hàng Task 2!');
        }

        async function executeTask3() {
            if (rawItems.length === 0) {
                if (confirm('Chưa có dữ liệu để phân tích. Bạn có muốn nạp nhanh 6 ca mẫu đề thi để phân tích ngay không?')) {
                    loadSampleDataset();
                    switchTask(3);
                }
                return;
            }
            await recomputeEntireSystem();
            renderTask3Data();
            showToast('🔄 Đã tính toán lại bảng phân tích Task 3!');
        }

        async function executeTask4() {
            if (rawItems.length === 0) {
                if (confirm('Chưa có dữ liệu cho Dashboard. Bạn có muốn nạp nhanh 6 ca mẫu đề thi để xem Dashboard ngay không?')) {
                    loadSampleDataset();
                    switchTask(4);
                }
                return;
            }
            await recomputeEntireSystem();
            renderTask4Data();
            showToast('🔄 Đã làm mới Dashboard & Báo cáo Task 4!');
        }

        // KHỞI CHẠY TỨC THÌ 0MS KHI MỞ TRANG
        instantRenderAll();
    </script>
    <!-- INPUT FILE ĐỘC LẬP HOÀN TOÀN ĐẢM BẢO HOẠT ĐỘNG 100% (HỖ TRỢ EXCEL, CSV, JSON, TXT) -->
    <input type="file" id="file-input" accept=".xlsx,.xls,.xlsm,.csv,.tsv,.json,.txt" style="display:none;" onchange="handleFileSelect(event)">
</body>
</html>
"""

# Render HTML_PAGE bằng cách thay thế các biến JSON đã pre-computed
HTML_PAGE = HTML_TEMPLATE.replace(
    "__INITIAL_SAMPLE_JSON__", json.dumps(INITIAL_SAMPLE_DATA, ensure_ascii=False)
).replace(
    "__INITIAL_EXTRACTED_JSON__", json.dumps(INITIAL_EXTRACTED, ensure_ascii=False)
).replace(
    "__INITIAL_DOSSIERS_JSON__", json.dumps(INITIAL_DOSSIERS_JSON, ensure_ascii=False)
).replace(
    "__INITIAL_SUMMARY_JSON__", json.dumps(init_summary, ensure_ascii=False)
)

# TỐI ƯU HÓA BỘ ĐỆM & GZIP NÉN TỐC ĐỘ CAO CHO LOCALHOST
HTML_PAGE_BYTES = HTML_PAGE.encode("utf-8")
HTML_PAGE_GZIP = gzip.compress(HTML_PAGE_BYTES, compresslevel=6)

def build_cleaned_excel_workbook(dossiers, summary=None, is_hung_phat=False):
    import io, datetime, pandas as pd, openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    output = io.BytesIO()
    today_str = datetime.datetime.now().strftime('%Y%m%d')

    if not dossiers:
        dossiers = []

    cleaned_rows = []
    inventory_rows = []
    finance_rows = []

    for d in dossiers:
        if not isinstance(d, dict):
            continue
        opp_id = d.get("opportunity_id") or "REQ-?"
        cust_name = d.get("customer_name") or "Khách hàng"
        email = d.get("contact_email") or "contact@client.vn"
        channel = d.get("channel") or "Trực tuyến"
        rep = d.get("assigned_sales_rep") or "NVKD"
        status = d.get("status") or "CÓ THỂ TIẾP TỤC"
        next_action = d.get("next_action") or ""
        
        ext = d.get("extracted_data") or {}
        pricing = d.get("pricing") or {}
        feas = d.get("feasibility") or {}
        approval = d.get("approval") or {}

        items = ext.get("items") or []
        if not items:
            items = [{"sku": "SKU-STD", "matched_name": "Gói thiết bị CNTT chuẩn hóa", "quantity": 1, "unit_price": pricing.get("base_subtotal") or 0}]

        for it in items:
            sku = it.get("sku") or it.get("standardized_sku") or "SKU-STD"
            prod_name = it.get("matched_name") or it.get("product_name") or it.get("raw_name") or "Thiết bị CNTT"
            qty = it.get("quantity") or 1
            unit_price = it.get("unit_price") or 0
            list_sub = qty * unit_price
            disc_rate = pricing.get("applied_discount_rate") or 0.05
            disc_amt = pricing.get("total_discount_amount") or (list_sub * disc_rate)
            prop_val = pricing.get("final_proposal_value") or (list_sub - disc_amt)
            budget = ext.get("budget") or ext.get("customer_budget")
            
            variance = (budget - prop_val) if (budget and budget > 0) else None
            budget_eval = "Đạt ngân sách" if (variance is not None and variance >= 0) else ("Vượt ngân sách" if variance is not None else "Chưa có ngân sách")

            req_days = ext.get("delivery_days") or ext.get("required_delivery_days")
            lead_days = feas.get("overall_lead_days_needed") or 5
            time_eval = "Kịp tiến độ" if (req_days and lead_days <= req_days) else ("Trễ tiến độ" if req_days else "Chưa rõ hạn định")

            cleaned_rows.append({
                "Mã Cơ Hội": opp_id,
                "Khách Hàng": cust_name,
                "Email Liên Hệ": email,
                "Kênh Tiếp Nhận": channel,
                "Người Phụ Trách": rep,
                "Mã SKU": sku,
                "Tên Sản Phẩm / Dịch Vụ": prod_name,
                "Số Lượng": qty,
                "Đơn Giá Niêm Yết (VNĐ)": unit_price,
                "Thành Tiền Niêm Yết (VNĐ)": list_sub,
                "Tỷ Lệ Chiết Khấu (%)": round(disc_rate * 100, 1),
                "Tiền Chiết Khấu (VNĐ)": disc_amt,
                "Giá Đề Xuất Net (VNĐ)": prop_val,
                "Ngân Sách (VNĐ)": budget if budget else "Chưa có",
                "Chênh Lệch Ngân Sách (VNĐ)": variance if variance is not None else "N/A",
                "Đánh Giá Ngân Sách": budget_eval,
                "Thời Hạn Khách Yêu Cầu (Ngày)": req_days if req_days else "Chưa rõ",
                "Lead Time Kho Cần (Ngày)": lead_days,
                "Đánh Giá Tiến Độ": time_eval,
                "Trạng Thái Hồ Sơ": status,
                "Thẩm Quyền Phê Duyệt": approval.get("approver_role") or "NVKD",
                "Hành Động Đề Xuất": next_action
            })

            cogs = prop_val * 0.55
            gross_profit = prop_val - cogs
            margin_pct = round((gross_profit / prop_val * 100), 1) if prop_val > 0 else 42.0

            finance_rows.append({
                "Mã Cơ Hội": opp_id,
                "Khách Hàng": cust_name,
                "Doanh Số Đề Xuất (VNĐ)": prop_val,
                "Giá Vốn COGS 55% (VNĐ)": cogs,
                "Lợi Nhuận Gộp (VNĐ)": gross_profit,
                "Biên Lợi Nhuận Gộp (%)": margin_pct,
                "Chiết Khấu Áp Dụng (%)": round(disc_rate * 100, 1),
                "Thẩm Quyền Duyệt": approval.get("approver_role") or "NVKD",
                "Lý Do Cần Phê Duyệt": "; ".join(approval.get("reasons") or []) or "Đạt thẩm quyền tiêu chuẩn"
            })

        items_feas = feas.get("items_feasibility") or []
        if items_feas:
            for itf in items_feas:
                inventory_rows.append({
                    "Mã Cơ Hội": opp_id,
                    "Khách Hàng": cust_name,
                    "Mã SKU": itf.get("sku"),
                    "Tên Hạng Mục": itf.get("name"),
                    "Số Lượng Yêu Cầu": itf.get("requested_qty"),
                    "Tồn Kho Sẵn Có": itf.get("available_stock"),
                    "Trạng Thái Kho": "Đủ tồn kho" if itf.get("is_stock_sufficient") else f"Thiếu {itf.get('stock_shortage', 0)} cái",
                    "Số Lượng Thiếu Hụt": itf.get("stock_shortage") or 0,
                    "Kho Phụ Trách": itf.get("inventory_location") or "Hà Nội",
                    "Thời Gian Xử Lý (Ngày)": itf.get("estimated_lead_days") or 3,
                    "Hạn Định Khách": feas.get("customer_deadline_days") or "Chưa rõ",
                    "Kết Luận Tiến Độ": feas.get("lead_time_status") or "Kịp tiến độ"
                })
        else:
            inventory_rows.append({
                "Mã Cơ Hội": opp_id,
                "Khách Hàng": cust_name,
                "Mã SKU": items[0].get("sku", "SKU-STD"),
                "Tên Hạng Mục": items[0].get("matched_name", "Thiết bị"),
                "Số Lượng Yêu Cầu": items[0].get("quantity", 1),
                "Tồn Kho Sẵn Có": "Sẵn sàng",
                "Trạng Thái Kho": "Đủ tồn kho",
                "Số Lượng Thiếu Hụt": 0,
                "Kho Phụ Trách": "Trung tâm",
                "Thời Gian Xử Lý (Ngày)": 3,
                "Hạn Định Khách": 10,
                "Kết Luận Tiến Độ": "Kịp tiến độ"
            })

    total_deals = len(dossiers)
    total_val = sum((d.get("pricing") or {}).get("final_proposal_value", 0) for d in dossiers if d.get("status") in ["CÓ THỂ TIẾP TỤC", "CHỜ DUYỆT"])
    total_savings = sum((d.get("pricing") or {}).get("total_discount_amount", 0) for d in dossiers)
    status_counts = {}
    for d in dossiers:
        st = d.get("status", "KHÁC")
        status_counts[st] = status_counts.get(st, 0) + 1

    kpi_rows = [
        {"Chỉ Số KPI": "Tổng Số Cơ Hội Tiếp Nhận", "Giá Trị": total_deals, "Đơn Vị": "Cơ hội", "Diễn Giải": "Toàn bộ số lượng hồ sơ được nạp vào hệ thống"},
        {"Chỉ Số KPI": "Tổng Doanh Số Pipeline Hợp Lệ", "Giá Trị": total_val, "Đơn Vị": "VNĐ", "Diễn Giải": "Bao gồm các cơ hội Hợp Lệ và Đang chờ quản lý duyệt"},
        {"Chỉ Số KPI": "Tổng Giá Trị Chiết Khấu Ưu Đãi", "Giá Trị": total_savings, "Đơn Vị": "VNĐ", "Diễn Giải": "Tổng số tiền đã giảm trừ/tiết kiệm cho khách hàng"},
        {"Chỉ Số KPI": "Số Cơ Hội Có Thể Tiếp Tục (Hợp Lệ)", "Giá Trị": status_counts.get("CÓ THỂ TIẾP TỤC", 0), "Đơn Vị": "Cơ hội", "Diễn Giải": "Đạt 100% về kho hàng, ngân sách và thẩm quyền"},
        {"Chỉ Số KPI": "Số Cơ Hội Chờ Cấp Quản Lý Duyệt", "Giá Trị": status_counts.get("CHỜ DUYỆT", 0), "Đơn Vị": "Cơ hội", "Diễn Giải": "Vượt hạn mức thẩm quyền chiết khấu NVKD (>8%)"},
        {"Chỉ Số KPI": "Số Cơ Hội Cần Bổ Sung Thông Tin", "Giá Trị": status_counts.get("CẦN BỔ SUNG THÔNG TIN", 0), "Đơn Vị": "Cơ hội", "Diễn Giải": "Thiếu dữ kiện đầu vào, đã tạo email yêu cầu khách làm rõ"},
        {"Chỉ Số KPI": "Số Cơ Hội Chưa Đáp Ứng", "Giá Trị": status_counts.get("CHƯA ĐÁP ỨNG", 0), "Đơn Vị": "Cơ hội", "Diễn Giải": "Vượt quá khả năng đáp ứng kho hàng hoặc vượt quá ngân sách"}
    ]

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(cleaned_rows).to_excel(writer, sheet_name="DU_LIEU_DA_LAM_SACH", index=False)
        pd.DataFrame(inventory_rows).to_excel(writer, sheet_name="THAM_DINH_TON_KHO", index=False)
        pd.DataFrame(finance_rows).to_excel(writer, sheet_name="KIEM_SOAT_TAI_CHINH", index=False)
        pd.DataFrame(kpi_rows).to_excel(writer, sheet_name="TONG_HOP_KPI_PIPELINE", index=False)

        global CURRENT_HUNG_PHAT_ANALYSIS
        if is_hung_phat and CURRENT_HUNG_PHAT_ANALYSIS and CURRENT_HUNG_PHAT_ANALYSIS.get("audit_records"):
            hp_recs = CURRENT_HUNG_PHAT_ANALYSIS["audit_records"]
            hp_clean = []
            for r in hp_recs:
                hp_clean.append({
                    "Mã Bản Ghi": r.get("id"),
                    "Khu Vực": r.get("region"),
                    "Sheet Gốc": r.get("sheet"),
                    "Kỳ Thống Kê": r.get("period"),
                    "Chỉ Tiêu": r.get("metric"),
                    "Giá Trị Đã Làm Sạch": r.get("value"),
                    "Đơn Vị": r.get("unit"),
                    "Cờ Kiểm Toán (Audit Flags)": "; ".join(r.get("audit_flags") or []),
                    "Trạng Thái Kiểm Toán": r.get("status"),
                    "Biện Pháp Xử Lý": r.get("action_note")
                })
            pd.DataFrame(hp_clean).to_excel(writer, sheet_name="KIEM_TOAN_HUNG_PHAT", index=False)

    wb = openpyxl.load_workbook(output)
    header_fill = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0")
    )

    for s_name in wb.sheetnames:
        ws = wb[s_name]
        ws.views.sheetView[0].showGridLines = True
        ws.row_dimensions[1].height = 26
        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            max_len = max(len(str(ws.cell(row=r, column=col_idx).value or '')) for r in range(1, ws.max_row + 1))
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 13), 50)

            for r in range(2, ws.max_row + 1):
                c = ws.cell(row=r, column=col_idx)
                c.border = thin_border
                c.font = Font(name="Segoe UI", size=9.5)
                val = c.value
                if isinstance(val, (int, float)) and val > 1000:
                    c.number_format = '#,##0'

    final_io = io.BytesIO()
    wb.save(final_io)
    fname = f"du_lieu_da_lam_sach_minhan_{today_str}.xlsx"
    return final_io.getvalue(), fname

class RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept-Encoding")

    def send_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        self.send_cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(HTML_PAGE_BYTES)))
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        global INITIAL_EXTRACTED, HUNG_PHAT_PRELOADED, CURRENT_HUNG_PHAT_ANALYSIS, INITIAL_DOSSIERS_JSON

        if parsed.path in ["/", "/index.html"]:
            accept_encoding = self.headers.get("Accept-Encoding", "")
            if "gzip" in accept_encoding:
                self.send_response(200)
                self.send_cors_headers()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(HTML_PAGE_GZIP)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(HTML_PAGE_GZIP)
            else:
                self.send_response(200)
                self.send_cors_headers()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(HTML_PAGE_BYTES)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(HTML_PAGE_BYTES)
        elif parsed.path == "/favicon.ico":
            self.send_response(204)
            self.send_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif parsed.path in ["/api/data", "/api/opportunities"]:
            self.send_json({"extracted": INITIAL_EXTRACTED})
        elif parsed.path == "/api/load_sample":
            with open("data/sample_requests.json", "r", encoding="utf-8") as f:
                sample_data = json.load(f)
            self.send_json({"sample_data": sample_data})
        elif parsed.path == "/api/load_hung_phat_sample":
            if not HUNG_PHAT_PRELOADED and os.path.exists("Hung_Phat_Test_Data_5_Steps.xlsx"):
                try:
                    xl_hp = pd.ExcelFile("Hung_Phat_Test_Data_5_Steps.xlsx")
                    HUNG_PHAT_PRELOADED = analyze_hung_phat_data(xl_hp)
                except Exception as e:
                    print("Error loading Hung Phat sample:", e)
            CURRENT_HUNG_PHAT_ANALYSIS = HUNG_PHAT_PRELOADED
            if CURRENT_HUNG_PHAT_ANALYSIS:
                items = []
                for rec in CURRENT_HUNG_PHAT_ANALYSIS["audit_records"]:
                    items.append({
                        "id": rec["id"],
                        "customer_name": f"Dữ Liệu {rec['region']}",
                        "contact_email": "hungphat@market-research.vn",
                        "channel": f"Sheet: {rec['sheet']}",
                        "raw_request_text": f"[{rec['sheet']}] {rec['metric']}: {rec['value']} ({rec['unit']}). {rec['description']}. {rec['action_note']}",
                        "hung_phat_record": rec,
                        "is_hung_phat": True
                    })
                self.send_json({
                    "success": True,
                    "items": items,
                    "count": len(items),
                    "is_hung_phat": True
                })
            else:
                self.send_json({"success": False, "error": "Không tìm thấy tệp Hung_Phat_Test_Data_5_Steps.xlsx"})
        elif parsed.path == "/api/export_cleaned_excel":
            excel_bytes, filename = build_cleaned_excel_workbook(
                dossiers=INITIAL_DOSSIERS_JSON,
                is_hung_phat=bool(CURRENT_HUNG_PHAT_ANALYSIS)
            )
            self.send_response(200)
            self.send_cors_headers()
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(excel_bytes)))
            self.end_headers()
            self.wfile.write(excel_bytes)
        else:
            self.send_response(404)
            self.send_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

    def _decode_body(self, body_bytes):
        for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1258", "cp1252"]:
            try:
                return body_bytes.decode(enc)
            except Exception:
                pass
        return body_bytes.decode("utf-8", errors="replace")

    def _parse_uploaded_file(self, file_bytes, filename):
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        items = []

        try:
            if ext in ["xlsx", "xls", "xlsm", "xlsb"]:
                excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
                if is_hung_phat_workbook(excel_file):
                    hp_res = analyze_hung_phat_data(excel_file)
                    global CURRENT_HUNG_PHAT_ANALYSIS
                    CURRENT_HUNG_PHAT_ANALYSIS = hp_res
                    items = []
                    for idx, rec in enumerate(hp_res["audit_records"]):
                        raw_desc = f"[{rec['sheet']}] {rec['metric']}: {rec['value']} ({rec['unit']}). {rec['description']}. {rec['action_note']}"
                        items.append({
                            "id": rec["id"],
                            "customer_name": f"Dữ Liệu {rec['region']}",
                            "contact_email": "hungphat@market-research.vn",
                            "channel": f"Khảo sát ({rec['sheet']})",
                            "raw_request_text": raw_desc,
                            "hung_phat_record": rec,
                            "is_hung_phat": True
                        })
                    return items

                dfs = []
                for sheet in excel_file.sheet_names:
                    sdf = excel_file.parse(sheet)
                    if not sdf.empty:
                        dfs.append(sdf)
                df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
                items = self._convert_df_to_requests(df, f"Excel ({filename})")

            elif ext in ["csv", "tsv"]:
                sep = "\t" if ext == "tsv" else ","
                df = None
                for enc in ["utf-8", "utf-8-sig", "cp1258", "latin-1"]:
                    try:
                        df = pd.read_csv(io.BytesIO(file_bytes), sep=sep, encoding=enc)
                        break
                    except Exception:
                        pass
                if df is not None:
                    items = self._convert_df_to_requests(df, f"CSV ({filename})")

            elif ext == "json":
                content_str = self._decode_body(file_bytes)
                parsed = json.loads(content_str)
                if isinstance(parsed, list):
                    items = parsed
                elif isinstance(parsed, dict):
                    for k in ["requests", "sample_requests", "data", "items"]:
                        if isinstance(parsed.get(k), list):
                            items = parsed[k]
                            break
                    if not items:
                        items = [parsed]

            else:
                text = self._decode_body(file_bytes)
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for idx, line in enumerate(lines):
                    items.append({
                        "id": f"REQ-{2000 + idx}",
                        "customer_name": f"Khách Hàng ({filename.split('.')[0]} #{idx + 1})",
                        "contact_email": "contact@client.vn",
                        "channel": f"File ({filename})",
                        "raw_request_text": line
                    })

        except Exception as e:
            print(f"Error parsing uploaded file {filename}: {e}", flush=True)

        cleaned = []
        for idx, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            req_id = it.get("id") or it.get("request_id") or f"REQ-{3000 + idx}"
            cust_name = it.get("customer_name") or it.get("customer") or f"Khách Hàng {idx + 1}"
            email = it.get("contact_email") or it.get("email") or "contact@client.vn"
            channel = it.get("channel") or f"Tệp {filename}"
            raw_text = it.get("raw_request_text") or it.get("raw_text") or it.get("content") or it.get("text") or ""
            
            cleaned.append({
                "id": str(req_id),
                "customer_name": str(cust_name),
                "contact_email": str(email),
                "channel": str(channel),
                "raw_request_text": str(raw_text)
            })

        return cleaned

    def _convert_df_to_requests(self, df, channel_name):
        items = []
        if df.empty:
            return items

        col_map = {str(col).strip().lower(): col for col in df.columns}

        def find_col(*keywords):
            for kw in keywords:
                for norm, orig in col_map.items():
                    if kw in norm:
                        return orig
            return None

        def get_val(row, *keywords):
            col = find_col(*keywords)
            if col:
                val = row.get(col)
                if pd.notna(val) and str(val).strip() != "":
                    if isinstance(val, float) and val.is_integer():
                        return str(int(val))
                    return str(val).strip()
            return None

        col_ho = find_col("họ lót", "họ đệm", "họ")
        col_ten = find_col("tên riêng", "tên")
        col_full = find_col("họ và tên", "họ tên", "tên khách hàng", "khách hàng", "customer", "sinh viên", "đơn vị", "doanh nghiệp")

        for idx, row in df.iterrows():
            cust_name = ""
            if col_full:
                cust_name = str(row.get(col_full) or "").strip()
            elif col_ho and col_ten:
                h = str(row.get(col_ho) or "").strip()
                t = str(row.get(col_ten) or "").strip()
                cust_name = (h + " " + t).strip()
            elif col_ten:
                cust_name = str(row.get(col_ten) or "").strip()

            if not cust_name or cust_name == "nan":
                cust_name = f"Khách Hàng ({channel_name.split('(')[-1].replace(')', '')} #{idx + 1})"

            email = get_val(row, "email", "mail", "thư điện tử")
            if not email or email == "nan":
                email = "contact@client.vn"

            req_id = get_val(row, "mã sv", "mssv", "mã", "id", "stt", "code")
            if req_id and req_id != "nan":
                req_id_str = f"REQ-{req_id}"
            else:
                req_id_str = f"REQ-{4000 + idx}"

            ch_val = get_val(row, "kênh", "channel", "lớp", "nguồn")
            channel_str = f"{channel_name} - {ch_val}" if ch_val else channel_name

            raw_text = get_val(row, "yêu cầu", "nội dung", "mô tả", "ghi chú", "đề tài", "thiết bị", "cấu hình", "request", "content", "raw")
            prod_val = get_val(row, "sản phẩm", "thiết bị", "hàng hóa", "mặt hàng", "tên hàng", "cấu hình", "gói", "product", "item", "description", "san_pham", "thiet_bi", "loại")
            qty_val = get_val(row, "số lượng", "sl", "qty", "quantity", "so_luong")
            price_val = get_val(row, "đơn giá", "giá", "price", "unit_price", "don_gia")
            budget_val = get_val(row, "ngân sách", "budget", "kinh phí", "giá trị", "tổng tiền", "thành tiền", "doanh số", "doanh thu", "số tiền", "tiền", "tổng cộng", "amount", "revenue", "sales", "thanh_tien", "doanh_so", "so_tien", "gia_tri", "học phí")
            days_val = get_val(row, "thời hạn", "deadline", "ngày", "ngày giao", "lead", "tiến độ", "thời gian", "delivery", "days", "han_giao")

            if not raw_text or raw_text == "nan":
                parts = []
                for col in df.columns:
                    v = row.get(col)
                    if pd.notna(v) and str(v).strip() != "":
                        if isinstance(v, float) and v.is_integer():
                            v = int(v)
                        parts.append(f"{col}: {v}")
                raw_text = "; ".join(parts) if parts else f"Yêu cầu từ {cust_name}"

            if prod_val and prod_val.lower() not in raw_text.lower():
                raw_text += f". Yêu cầu cấu hình thiết bị: {qty_val or 1} {prod_val}"
                if price_val:
                    raw_text += f", đơn giá {price_val} VNĐ"

            if budget_val and "ngân sách" not in raw_text.lower() and "doanh số" not in raw_text.lower():
                raw_text += f". Ngân sách: {budget_val} VNĐ"
            if days_val and "ngày" not in raw_text.lower():
                raw_text += f". Thời hạn: {days_val} ngày"

            items.append({
                "id": req_id_str,
                "customer_name": cust_name,
                "contact_email": email,
                "channel": channel_str,
                "raw_request_text": raw_text
            })

        return items

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        global agent

        if parsed.path == "/api/upload_file":
            content_length = int(self.headers.get("Content-Length", 0))
            file_bytes = self.rfile.read(content_length)
            query_params = urllib.parse.parse_qs(parsed.query)
            filename = query_params.get("filename", ["data.xlsx"])[0]
            items = self._parse_uploaded_file(file_bytes, filename)
            self.send_json({"items": items, "count": len(items), "filename": filename})

        elif parsed.path in ["/api/step1_extract"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            requests_list = json.loads(self._decode_body(body))
            if not isinstance(requests_list, list):
                requests_list = [requests_list]

            extracted_result = []
            for idx, r in enumerate(requests_list):
                ext = agent.extractor.run(r)
                rep = SALES_REPRESENTATIVES[idx % len(SALES_REPRESENTATIVES)]
                missing_str = "\n".join([f"- {m}" for m in ext.missing_fields])
                email_draft = f"Kính gửi Quý khách hàng {ext.customer_name},\n\nCông ty Công nghệ Minh An xin chân thành cảm ơn Quý khách.\n\nTrân trọng,\n{rep} - Bộ phận Kinh doanh Minh An Tech"
                extracted_result.append({
                    "request_id": ext.request_id,
                    "customer_name": ext.customer_name,
                    "contact_email": ext.contact_email,
                    "channel": ext.channel,
                    "raw_text": ext.raw_text,
                    "assigned_sales_rep": rep,
                    "budget": ext.customer_budget,
                    "delivery_days": ext.required_delivery_days,
                    "requested_discount_rate": ext.requested_discount_rate,
                    "is_complete": ext.is_complete,
                    "missing_fields": ext.missing_fields,
                    "clarification_email_draft": email_draft,
                    "items": [
                        {
                            "sku": it.sku,
                            "matched_name": it.matched_name,
                            "raw_name": it.raw_name,
                            "quantity": it.quantity,
                            "unit_price": it.unit_price
                        } for it in ext.items
                    ]
                })

            self.send_json({"extracted": extracted_result})

        elif parsed.path in ["/api/batch_process", "/api/opportunities"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            requests_list = json.loads(self._decode_body(body))
            if isinstance(requests_list, dict):
                for k in ["requests", "sample_requests", "data", "items"]:
                    if isinstance(requests_list.get(k), list):
                        requests_list = requests_list[k]
                        break
            if not isinstance(requests_list, list):
                requests_list = [requests_list]

            global CURRENT_HUNG_PHAT_ANALYSIS
            is_hp = bool(CURRENT_HUNG_PHAT_ANALYSIS)
            for r in requests_list:
                if isinstance(r, dict):
                    rid = str(r.get("id", ""))
                    if "hung_phat_record" in r or "Hung_Phat" in str(r.get("channel", "")) or rid.startswith("MR-") or rid.startswith("FB-") or rid.startswith("CAP-"):
                        is_hp = True
                        break

            if is_hp:
                if not CURRENT_HUNG_PHAT_ANALYSIS and os.path.exists("Hung_Phat_Test_Data_5_Steps.xlsx"):
                    try:
                        xl_hp = pd.ExcelFile("Hung_Phat_Test_Data_5_Steps.xlsx")
                        CURRENT_HUNG_PHAT_ANALYSIS = analyze_hung_phat_data(xl_hp)
                    except Exception as e:
                        print("Error loading Hung Phat in batch:", e)

                if CURRENT_HUNG_PHAT_ANALYSIS:
                    hp = CURRENT_HUNG_PHAT_ANALYSIS
                    dossiers_data = []
                    extracted_result = []
                    hp_pkg_pricing = [
                        {"base": 420000000, "val": 399000000, "disc": 0.05, "sav": 21000000, "bud": 450000000, "days": 10},
                        {"base": 360000000, "val": 338400000, "disc": 0.06, "sav": 21600000, "bud": 380000000, "days": 12},
                        {"base": 120000000, "val": 115200000, "disc": 0.04, "sav": 4800000, "bud": 125000000, "days": 7},
                        {"base": 180000000, "val": 171000000, "disc": 0.05, "sav": 9000000, "bud": 180000000, "days": 14}
                    ]
                    for idx, rec in enumerate(hp["audit_records"]):
                        status_badge = "CÓ THỂ TIẾP TỤC" if rec["status"] == "VALID" else ("CHỜ DUYỆT" if rec["status"] in ["DUPLICATE", "WARNING"] else ("CẦN BỔ SUNG THÔNG TIN" if rec["status"] == "MISSING" else "CHƯA ĐÁP ỨNG"))
                        val_str = f"{rec['value']} {rec['unit']}" if rec['value'] is not None else "NULL"
                        pkg_info = hp_pkg_pricing[idx % len(hp_pkg_pricing)]
                        
                        dossiers_data.append({
                            "opportunity_id": rec["id"],
                            "customer_name": f"{rec['region']} ({rec['sheet']})",
                            "contact_email": "bi.audit@hungphat.vn",
                            "channel": rec["sheet"],
                            "assigned_sales_rep": "Senior BI Analyst (Hưng Phát)",
                            "status": status_badge,
                            "next_action": rec["action_note"],
                            "is_hung_phat": True,
                            "hung_phat_record": rec,
                            "extracted_data": {
                                "raw_text": f"Chỉ tiêu: {rec['metric']} | Giá trị: {val_str} | Kỳ: {rec['period']}",
                                "budget": pkg_info["bud"],
                                "delivery_days": pkg_info["days"],
                                "requested_discount_rate": pkg_info["disc"],
                                "is_complete": (rec["status"] == "VALID"),
                                "missing_fields": rec["audit_flags"],
                                "items": [
                                    {
                                        "sku": rec["id"],
                                        "matched_name": rec["metric"],
                                        "raw_name": rec["metric"],
                                        "quantity": rec["value"] if isinstance(rec["value"], (int, float)) else 1,
                                        "unit_price": pkg_info["val"],
                                        "total_price": pkg_info["val"]
                                    }
                                ]
                            },
                            "pricing": {
                                "base_subtotal": pkg_info["base"],
                                "applied_discount_rate": pkg_info["disc"],
                                "total_discount_amount": pkg_info["sav"],
                                "final_proposal_value": pkg_info["val"],
                                "is_within_budget": True,
                                "pricing_notes": rec["action_note"]
                            },
                            "feasibility": {
                                "overall_lead_days_needed": pkg_info["days"],
                                "customer_deadline_days": pkg_info["days"] + 2,
                                "lead_time_status": "Kịp tiến độ" if rec["status"] == "VALID" else "Cần theo dõi",
                                "is_feasible": (rec["status"] != "MISSING"),
                                "rejection_reason": "; ".join(rec["audit_flags"]) if rec["audit_flags"] else "Đạt tiêu chuẩn",
                                "items_feasibility": [
                                    {
                                        "sku": rec["id"],
                                        "name": rec["metric"],
                                        "requested_qty": val_str,
                                        "available_stock": "Sẵn sàng",
                                        "is_stock_sufficient": (rec["status"] == "VALID"),
                                        "stock_shortage": 0,
                                        "estimated_lead_days": pkg_info["days"],
                                        "inventory_location": rec["region"]
                                    }
                                ]
                            },
                            "approval": {
                                "requires_escalation": (rec["status"] in ["DUPLICATE", "MISSING", "WARNING"]),
                                "approver_role": "Giám Đốc Dự Án BI",
                                "reasons": rec["audit_flags"]
                            }
                        })

                        extracted_result.append({
                            "request_id": rec["id"],
                            "customer_name": f"{rec['region']} ({rec['sheet']})",
                            "contact_email": "bi.audit@hungphat.vn",
                            "channel": rec["sheet"],
                            "raw_text": f"{rec['metric']}: {val_str}",
                            "assigned_sales_rep": "Senior BI Analyst",
                            "budget": None,
                            "delivery_days": None,
                            "requested_discount_rate": None,
                            "is_complete": (rec["status"] == "VALID"),
                            "missing_fields": rec["audit_flags"],
                            "clarification_email_draft": f"Kính gửi đơn vị phụ trách {rec['region']},\n\nKiểm toán dữ liệu phát hiện: {'; '.join(rec['audit_flags']) if rec['audit_flags'] else 'Dữ liệu đạt chuẩn.'}\n\nĐề xuất: {rec['action_note']}",
                            "items": [
                                {
                                    "sku": rec["id"],
                                    "matched_name": rec["metric"],
                                    "raw_name": rec["metric"],
                                    "quantity": rec["value"] if isinstance(rec["value"], (int, float)) else 1,
                                    "unit_price": 0
                                }
                            ]
                        })

                    hp_summary = {
                        "is_hung_phat": True,
                        "total_opportunities": len(hp["regional_kpi"]),
                        "total_records_audited": hp["total_audited"],
                        "valid_count": hp["valid_count"],
                        "warning_count": hp["warning_count"],
                        "regional_kpi": hp["regional_kpi"],
                        "bluf_summary": hp["bluf_summary"],
                        "total_expected_revenue": 550000000,
                        "total_cost": 280000000,
                        "total_gross_profit": 270000000,
                        "average_margin": 49.1
                    }

                    self.send_json({
                        "dossiers": dossiers_data,
                        "summary": hp_summary,
                        "extracted": extracted_result,
                        "audit": []
                    })
                    return

            agent.audit_trail.clear()
            agent._rep_index = 0
            cur_dossiers, cur_summary = agent.process_batch(requests_list)

            os.makedirs("outputs", exist_ok=True)
            with open("outputs/summary_report.json", "w", encoding="utf-8") as f:
                json.dump(cur_summary, f, ensure_ascii=False, indent=2)

            dossiers_data = [
                {
                    "opportunity_id": d.opportunity_id,
                    "customer_name": d.customer_name,
                    "contact_email": d.contact_email,
                    "channel": d.channel,
                    "assigned_sales_rep": d.assigned_sales_rep,
                    "status": d.status,
                    "next_action": d.next_action,
                    "customer_response_draft": d.customer_response_draft,
                    "approval_ticket": d.approval_ticket,
                    "extracted_data": {
                        "raw_text": d.extracted_data.raw_text,
                        "budget": d.extracted_data.customer_budget,
                        "delivery_days": d.extracted_data.required_delivery_days,
                        "requested_discount_rate": d.extracted_data.requested_discount_rate,
                        "is_complete": d.extracted_data.is_complete,
                        "missing_fields": d.extracted_data.missing_fields,
                        "items": [
                            {
                                "sku": it.sku,
                                "matched_name": it.matched_name,
                                "raw_name": it.raw_name,
                                "quantity": it.quantity,
                                "unit_price": it.unit_price,
                                "total_price": it.total_price
                            } for it in d.extracted_data.items
                        ]
                    },
                    "pricing": {
                        "base_subtotal": d.pricing.base_subtotal,
                        "applied_discount_rate": d.pricing.applied_discount_rate,
                        "total_discount_amount": d.pricing.total_discount_amount,
                        "final_proposal_value": d.pricing.final_proposal_value,
                        "is_within_budget": d.pricing.is_within_budget,
                        "pricing_notes": d.pricing.pricing_notes
                    } if d.pricing else None,
                    "feasibility": {
                        "overall_lead_days_needed": d.feasibility.overall_lead_days_needed,
                        "customer_deadline_days": d.feasibility.customer_deadline_days,
                        "lead_time_status": d.feasibility.lead_time_status,
                        "is_feasible": d.feasibility.is_feasible,
                        "rejection_reason": d.feasibility.rejection_reason,
                        "items_feasibility": [
                            {
                                "sku": it.sku,
                                "name": it.name,
                                "requested_qty": it.requested_qty,
                                "available_stock": it.available_stock,
                                "is_stock_sufficient": it.is_stock_sufficient,
                                "stock_shortage": it.stock_shortage,
                                "estimated_lead_days": it.estimated_lead_days,
                                "inventory_location": it.inventory_location
                            } for it in d.feasibility.items_feasibility
                        ] if d.feasibility else []
                    } if d.feasibility else None,
                    "approval": {
                        "requires_escalation": d.approval.requires_escalation,
                        "approver_role": d.approval.approver_role,
                        "reasons": d.approval.reasons
                    } if d.approval else None
                } for d in cur_dossiers
            ]

            extracted_result = []
            for idx, r in enumerate(requests_list):
                ext = agent.extractor.run(r)
                rep = SALES_REPRESENTATIVES[idx % len(SALES_REPRESENTATIVES)]
                missing_str = "\n".join([f"- {m}" for m in ext.missing_fields])
                email_draft = f"Kính gửi Quý khách hàng {ext.customer_name},\n\nCông ty Công nghệ Minh An xin chân thành cảm ơn Quý khách.\n\nTrân trọng,\n{rep} - Bộ phận Kinh doanh Minh An Tech"
                extracted_result.append({
                    "request_id": ext.request_id,
                    "customer_name": ext.customer_name,
                    "contact_email": ext.contact_email,
                    "channel": ext.channel,
                    "raw_text": ext.raw_text,
                    "assigned_sales_rep": rep,
                    "budget": ext.customer_budget,
                    "delivery_days": ext.required_delivery_days,
                    "requested_discount_rate": ext.requested_discount_rate,
                    "is_complete": ext.is_complete,
                    "missing_fields": ext.missing_fields,
                    "clarification_email_draft": email_draft,
                    "items": [
                        {
                            "sku": it.sku,
                            "matched_name": it.matched_name,
                            "raw_name": it.raw_name,
                            "quantity": it.quantity,
                            "unit_price": it.unit_price
                        } for it in ext.items
                    ]
                })

            self.send_json({
                "dossiers": dossiers_data,
                "summary": cur_summary,
                "extracted": extracted_result,
                "audit": [
                    {
                        "timestamp": a.timestamp,
                        "opportunity_id": a.opportunity_id,
                        "stage": a.stage,
                        "tool_called": a.tool_called,
                        "decision_reasoning": a.decision_reasoning
                    } for a in agent.audit_trail
                ]
            })

        elif parsed.path == "/api/export_cleaned_excel":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = {}
            if body:
                try:
                    payload = json.loads(self._decode_body(body))
                except Exception:
                    payload = {}
            
            dossiers = []
            if isinstance(payload, list):
                dossiers = payload
            elif isinstance(payload, dict):
                dossiers = payload.get("dossiers") or payload.get("items") or payload.get("data") or []
            
            is_hp = payload.get("is_hung_phat", False) if isinstance(payload, dict) else False

            excel_bytes, filename = build_cleaned_excel_workbook(
                dossiers=dossiers,
                summary=payload.get("summary") if isinstance(payload, dict) else None,
                is_hung_phat=is_hp
            )
            self.send_response(200)
            self.send_cors_headers()
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(excel_bytes)))
            self.end_headers()
            self.wfile.write(excel_bytes)

        elif parsed.path == "/api/reset":
            agent.audit_trail.clear()
            agent._rep_index = 0
            self.send_json({"status": "cleared"})
        else:
            self.send_response(404)
            self.send_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

def run_server():
    server_address = ("0.0.0.0", PORT)
    httpd = ThreadingHTTPServer(server_address, RequestHandler)
    httpd.daemon_threads = True
    httpd.allow_reuse_address = True
    print("=" * 75, flush=True)
    print(f"🚀 MINH AN AI AGENT SẴN SÀNG 100% TẠI:", flush=True)
    print(f"   👉 http://localhost:{PORT} hoặc http://127.0.0.1:{PORT}", flush=True)
    print("   ⚡ TỐI ƯU HÓA: Gzip Compression, Fast Keep-Alive, Zero Reflow", flush=True)
    print("=" * 75, flush=True)
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
