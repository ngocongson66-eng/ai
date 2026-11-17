import os
import json
from datetime import datetime
from typing import List, Dict, Any, Tuple
from src.models import (
    ExtractedRequest, OpportunityDossier, AuditLogEntry, ApprovalCheckResult
)
from src.tools import (
    InformationExtractionTool, InventoryLeadTimeTool,
    PricingDiscountTool, ApprovalRoutingTool, DocumentGenerationTool
)

SALES_REPRESENTATIVES = [
    "NVKD 01 - Nguyễn Văn An",
    "NVKD 02 - Trần Thị Bích",
    "NVKD 03 - Lê Hoàng Long",
    "NVKD 04 - Phạm Minh Tuấn",
    "NVKD 05 - Vũ Mai Phương",
    "NVKD 06 - Đỗ Quang Hưng"
]

class MinhAnSalesAgent:
    """
    AI Agent điều phối quy trình xử lý cơ hội bán hàng B2B cho Công ty Minh An.
    Tích hợp các công cụ nghiệp vụ, lưu vết audit log và tuân thủ chặt chẽ
    quy tắc phân quyền, kiểm soát rủi ro không tự xác nhận bán hàng vượt quyền.
    """
    def __init__(self, catalog_path: str, inventory_path: str, policies_path: str):
        with open(catalog_path, "r", encoding="utf-8") as f:
            self.catalog = json.load(f)
        with open(inventory_path, "r", encoding="utf-8") as f:
            self.inventory = json.load(f)
        with open(policies_path, "r", encoding="utf-8") as f:
            self.policies = json.load(f)

        # Khởi tạo các công cụ chuyên trách (Agent Tools / Business Skills)
        self.extractor = InformationExtractionTool(self.catalog, self.policies)
        self.inventory_tool = InventoryLeadTimeTool(self.inventory, self.policies)
        self.pricing_tool = PricingDiscountTool(self.policies)
        self.approval_tool = ApprovalRoutingTool(self.policies)
        self.doc_tool = DocumentGenerationTool()

        self.audit_trail: List[AuditLogEntry] = []
        self._rep_index = 0

    def _get_next_rep(self) -> str:
        rep = SALES_REPRESENTATIVES[self._rep_index % len(SALES_REPRESENTATIVES)]
        self._rep_index += 1
        return rep

    def _log_audit(self, opp_id: str, stage: str, tool_name: str, inputs: Dict[str, Any], outputs: Dict[str, Any], reasoning: str):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = AuditLogEntry(
            timestamp=now_str,
            opportunity_id=opp_id,
            stage=stage,
            tool_called=tool_name,
            inputs=inputs,
            outputs=outputs,
            decision_reasoning=reasoning
        )
        self.audit_trail.append(entry)

    def process_request(self, raw_request: Dict[str, Any]) -> OpportunityDossier:
        opp_id = (
            raw_request.get("id") or
            raw_request.get("request_id") or
            raw_request.get("opportunity_id") or
            raw_request.get("ma_yeu_cau") or
            "OPP-UNKNOWN"
        )
        customer_name = (
            raw_request.get("customer_name") or
            raw_request.get("customer") or
            raw_request.get("client_name") or
            raw_request.get("ten_khach_hang") or
            "Khách hàng B2B"
        )
        contact_email = (
            raw_request.get("contact_email") or
            raw_request.get("email") or
            raw_request.get("contact") or
            ""
        )
        channel = (
            raw_request.get("channel") or
            raw_request.get("kenh") or
            "Email"
        )

        # -------------------------------------------------------------
        # BƯỚC 1: Tiếp nhận yêu cầu & Phân loại & Kiểm tra thông tin
        # -------------------------------------------------------------
        extracted: ExtractedRequest = self.extractor.run(raw_request)
        
        self._log_audit(
            opp_id=opp_id,
            stage="Bước 1: Phân loại & Kiểm tra thông tin",
            tool_name="InformationExtractionTool",
            inputs={"raw_text": raw_request.get("raw_request_text", "")},
            outputs={
                "items_count": len(extracted.items),
                "budget": extracted.customer_budget,
                "delivery_days": extracted.required_delivery_days,
                "requested_discount": extracted.requested_discount_rate,
                "is_complete": extracted.is_complete,
                "missing_fields": extracted.missing_fields
            },
            reasoning=f"Agent phân tích văn bản tự nhiên: {'Đầy đủ thông tin tiên quyết' if extracted.is_complete else 'Thiếu thông tin: ' + ', '.join(extracted.missing_fields)}."
        )

        # -------------------------------------------------------------
        # RẼ NHÁNH: "Có đủ thông tin?"
        # -------------------------------------------------------------
        if not extracted.is_complete:
            assigned_rep = self._get_next_rep()
            status = "CẦN BỔ SUNG THÔNG TIN"
            next_action = "Gửi email yêu cầu khách hàng bổ sung thông tin còn thiếu; lưu hồ sơ tạm thời để NVKD theo dõi."
            
            # Thẩm định kho & báo giá CHỈ KHI có dữ liệu sản phẩm thực tế đầu vào (Không bịa đặt)
            feasibility = None
            pricing = None
            approval = None
            if extracted.items:
                feasibility = self.inventory_tool.run(extracted.items, extracted.required_delivery_days or 10)
                pricing = self.pricing_tool.run(extracted.items, extracted.customer_budget or 0, extracted.requested_discount_rate)
                approval = self.approval_tool.run(pricing, feasibility)

            dossier = OpportunityDossier(
                opportunity_id=opp_id,
                customer_name=customer_name,
                contact_email=contact_email,
                channel=channel,
                assigned_sales_rep=assigned_rep,
                status=status,
                extracted_data=extracted,
                feasibility=feasibility,
                pricing=pricing,
                approval=approval,
                next_action=next_action
            )
            dossier.customer_response_draft = self.doc_tool.draft_customer_response(dossier)
            
            self._log_audit(
                opp_id=opp_id,
                stage="Bước 2: Rẽ nhánh thông tin thiếu",
                tool_name="DocumentGenerationTool.draft_customer_response",
                inputs={"status": status, "missing_fields": extracted.missing_fields},
                outputs={"draft_generated": True},
                reasoning="Yêu cầu chưa đủ dữ kiện để thẩm định kho và tính giá chính thức. Đã lập ước tính sơ bộ và chuyển sang quy trình xin thông tin bổ sung."
            )
            return dossier

        # Nếu CÓ ĐỦ THÔNG TIN: Tạo Hồ sơ Cơ hội & Gắn người phụ trách
        assigned_rep = self._get_next_rep()

        # -------------------------------------------------------------
        # BƯỚC 3: Thẩm định tồn kho & Lead time (Hợp tác với Vận hành)
        # -------------------------------------------------------------
        feasibility = self.inventory_tool.run(extracted.items, extracted.required_delivery_days)
        
        self._log_audit(
            opp_id=opp_id,
            stage="Bước 3: Thẩm định tồn kho & thời gian đáp ứng",
            tool_name="InventoryLeadTimeTool",
            inputs={"items": [item.sku for item in extracted.items], "customer_days": extracted.required_delivery_days},
            outputs={
                "lead_time_status": feasibility.lead_time_status,
                "overall_lead_days_needed": feasibility.overall_lead_days_needed,
                "is_feasible": feasibility.is_feasible
            },
            reasoning=f"Hệ thống kho: Cần {feasibility.overall_lead_days_needed} ngày so với yêu cầu {extracted.required_delivery_days} ngày. Kết luận: {feasibility.lead_time_status}."
        )

        # -------------------------------------------------------------
        # BƯỚC 4: Lập Báo giá & Dự thảo đề xuất
        # -------------------------------------------------------------
        pricing = self.pricing_tool.run(
            items=extracted.items,
            requested_discount=extracted.requested_discount_rate,
            budget=extracted.customer_budget
        )

        self._log_audit(
            opp_id=opp_id,
            stage="Bước 4: Tính toán giá & chiết khấu",
            tool_name="PricingDiscountTool",
            inputs={
                "base_subtotal": pricing.base_subtotal,
                "applied_discount_rate": pricing.applied_discount_rate,
                "customer_budget": extracted.customer_budget
            },
            outputs={
                "final_proposal_value": pricing.final_proposal_value,
                "budget_variance": pricing.budget_variance,
                "is_within_budget": pricing.is_within_budget
            },
            reasoning=f"Áp dụng chiết khấu {pricing.applied_discount_rate*100:.1f}%. Giá trị ròng: {pricing.final_proposal_value:,.0f} VNĐ. Ngân sách KH: {extracted.customer_budget:,.0f} VNĐ."
        )

        # -------------------------------------------------------------
        # ĐÁNH GIÁ KHẢ NĂNG ĐÁP ỨNG TOÀN DIỆN
        # -------------------------------------------------------------
        # Nếu lead time không kịp HOẶC ngân sách khách hàng quá thấp (thâm hụt nghiêm trọng > 35%)
        is_budget_severely_deficient = (
            extracted.customer_budget is not None and 
            pricing.final_proposal_value > extracted.customer_budget * 1.35
        )

        if not feasibility.is_feasible or is_budget_severely_deficient:
            status = "CHƯA ĐÁP ỨNG"
            reason_parts = []
            if not feasibility.is_feasible:
                reason_parts.append(feasibility.rejection_reason or "Không đáp ứng tiến độ")
            if is_budget_severely_deficient:
                reason_parts.append(f"Ngân sách khách hàng ({extracted.customer_budget:,.0f} VNĐ) thấp hơn rất nhiều so với giá trị tối thiểu của hệ thống ({pricing.final_proposal_value:,.0f} VNĐ).")
            
            feasibility.rejection_reason = " | ".join(reason_parts)
            next_action = "NVKD liên hệ trực tiếp với khách hàng để đề xuất giãn thời gian giao hàng hoặc thay đổi cấu hình phương án thiết bị tương đương."

            dossier = OpportunityDossier(
                opportunity_id=opp_id,
                customer_name=customer_name,
                contact_email=contact_email,
                channel=channel,
                assigned_sales_rep=assigned_rep,
                status=status,
                extracted_data=extracted,
                feasibility=feasibility,
                pricing=pricing,
                approval=ApprovalCheckResult(requires_escalation=False, approver_role="NVKD", reasons=["Không đáp ứng yêu cầu kỹ thuật/vận hành"]),
                next_action=next_action
            )
            dossier.customer_response_draft = self.doc_tool.draft_customer_response(dossier)

            self._log_audit(
                opp_id=opp_id,
                stage="Bước 5: Đánh giá khả năng đáp ứng",
                tool_name="RuleEvaluation.FeasibilityCheck",
                inputs={"is_lead_feasible": feasibility.is_feasible, "budget_deficient": is_budget_severely_deficient},
                outputs={"status": status},
                reasoning="Yêu cầu không khả thi về thời hạn hoặc ngân sách không tiệm cận. Dừng báo giá cam kết, chuyển sang tư vấn giải pháp thay thế."
            )
            return dossier

        # -------------------------------------------------------------
        # BƯỚC 5: Kiểm tra Thẩm quyền & Chiết khấu đặc biệt
        # -------------------------------------------------------------
        approval = self.approval_tool.run(pricing, feasibility)

        self._log_audit(
            opp_id=opp_id,
            stage="Bước 6: Kiểm tra thẩm quyền phê duyệt",
            tool_name="ApprovalRoutingTool",
            inputs={"applied_discount": pricing.applied_discount_rate, "total_value": pricing.final_proposal_value},
            outputs={"requires_escalation": approval.requires_escalation, "approver_role": approval.approver_role, "reasons": approval.reasons},
            reasoning=f"Đánh giá phân quyền: {'Cần trình cấp ' + approval.approver_role + ' duyệt' if approval.requires_escalation else 'Trong hạn mức thẩm quyền của NVKD'}."
        )

        if approval.requires_escalation:
            status = "CHỜ DUYỆT"
            next_action = f"Lập Phiếu trình duyệt chuyển {approval.approver_role} xem xét phê duyệt. Tạm dừng phát hành báo giá chính thức để bảo đảm không vượt quyền."
        else:
            status = "CÓ THỂ TIẾP TỤC"
            next_action = "NVKD gửi Báo giá chính thức và Dự thảo đề xuất cho khách hàng; lên lịch gọi chăm sóc và theo dõi tiến trình ký hợp đồng."

        dossier = OpportunityDossier(
            opportunity_id=opp_id,
            customer_name=customer_name,
            contact_email=contact_email,
            channel=channel,
            assigned_sales_rep=assigned_rep,
            status=status,
            extracted_data=extracted,
            feasibility=feasibility,
            pricing=pricing,
            approval=approval,
            next_action=next_action
        )

        dossier.customer_response_draft = self.doc_tool.draft_customer_response(dossier)
        if status == "CHỜ DUYỆT":
            dossier.approval_ticket = self.doc_tool.generate_approval_ticket(dossier)

        return dossier

    def process_batch(self, requests_list: List[Dict[str, Any]]) -> Tuple[List[OpportunityDossier], Dict[str, Any]]:
        """Xử lý danh sách các yêu cầu và tổng hợp báo cáo chỉ số."""
        dossiers = []
        for req in requests_list:
            dossier = self.process_request(req)
            dossiers.append(dossier)

        # Tính toán bảng tổng hợp
        status_counts = {
            "CÓ THỂ TIẾP TỤC": 0,
            "CẦN BỔ SUNG THÔNG TIN": 0,
            "CHƯA ĐÁP ỨNG": 0,
            "CHỜ DUYỆT": 0
        }
        total_value_eligible_and_pending = 0.0

        for d in dossiers:
            if d.status in status_counts:
                status_counts[d.status] += 1
            if d.status in ["CÓ THỂ TIẾP TỤC", "CHỜ DUYỆT"] and d.pricing:
                total_value_eligible_and_pending += d.pricing.final_proposal_value

        summary = {
            "total_requests": len(dossiers),
            "status_counts": status_counts,
            "total_value_eligible_and_pending_vnd": total_value_eligible_and_pending,
            "total_value_formatted": f"{total_value_eligible_and_pending:,.0f} VNĐ"
        }

        return dossiers, summary
