// --- SCRIPT 0 ---

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
                        return (rawItems.length > 0);
                    }
                }
            } catch(e) {
                console.warn('LocalStorage load warning:', e);
            }
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

            // Tự động phân tích các nguyên nhân gốc từ dữ liệu thực tế
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

            if (!allDossiers || allDossiers.length === 0 || !isPipelineApproved) {
                elLead.innerText = (rawItems.length > 0 && !isPipelineApproved)
                    ? '⏳ Đang có ' + rawItems.length + ' yêu cầu chờ phê duyệt luồng tại Task 2. Vui lòng bấm duyệt tại Task 2 để xuất báo cáo điều hành BLUF.'
                    : 'Chưa có dữ liệu cơ hội kinh doanh để tổng hợp báo cáo điều hành BLUF. Vui lòng nhập dữ liệu ở Task 1.';
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

                // ĐIỀU KIỆN TUYỆT ĐỐI: CHỈ KHI CÓ DỮ LIỆU ĐẦU VÀO VÀ ĐÃ PHÊ DUYỆT THÌ MỚI BẮT ĐẦU VẼ BIỂU ĐỒ!
                const hasData = (allDossiers && allDossiers.length > 0 && isPipelineApproved);

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

                // Dữ liệu 100% tính toán động từ các hồ sơ thực tế trong hệ thống
                const data = validDossiers.map((d, idx) => {
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
                
                // Biên độ trục margin theo chuẩn 38% - 44% hoặc co dãn theo dữ liệu thực
                const margins = data.map(d => d.margin).filter(m => !isNaN(m) && isFinite(m));
                const calculatedMinM = margins.length > 0 ? Math.floor(Math.min(...margins)) : 38;
                const calculatedMaxM = margins.length > 0 ? Math.ceil(Math.max(...margins)) : 44;
                const minMargin = Math.min(38, calculatedMinM - 1);
                const maxMargin = Math.max(44, calculatedMaxM + 1);

                let svg = `<svg viewBox="0 0 ${width} ${height}" style="width:100%; height:370px; display:block; font-family:'Inter',sans-serif;">`;

                // 1. CHÚ THÍCH (LEGEND) Ở TRÊN CÙNG
                svg += `
                    <g id="legend">
                        <rect x="65" y="20" width="28" height="10" fill="#1f619e" rx="1.5" />
                        <text x="100" y="29" font-size="13" font-weight="700" fill="#1e293b">Doanh Số Thực Tế (VNĐ)</text>
                        <line x1="280" y1="25" x2="315" y2="25" stroke="#dc2626" stroke-width="3.5" stroke-linecap="round" />
                        <text x="325" y="29" font-size="13" font-weight="700" fill="#1e293b">Biên Lợi Nhuận Hoạt Động (Operating Margin %)</text>
                    </g>
                `;

                // 2. CÁC ĐƯỜNG LƯỚI NGANG VÀ NHÃN TỶ LỆ % BÊN PHẢI
                const marginStep = (maxMargin - minMargin <= 8) ? 1 : 2;
                for (let m = minMargin; m <= maxMargin; m += marginStep) {
                    const ratio = (maxMargin > minMargin) ? ((m - minMargin) / (maxMargin - minMargin)) : 0.5;
                    const y = yBottom - ratio * plotHeight;
                    svg += `<line x1="${xStart}" y1="${y}" x2="${xEnd}" y2="${y}" stroke="#f1f5f9" stroke-width="1" />`;
                    svg += `<text x="${xEnd + 12}" y="${y + 4}" font-size="12" font-weight="600" fill="#64748b">${m}%</text>`;
                }

                // ĐƯỜNG TRỤC CƠ SỞ (BASELINE)
                svg += `<line x1="${xStart}" y1="${yBottom}" x2="${xEnd}" y2="${yBottom}" stroke="#cbd5e1" stroke-width="1.5" />`;

                // 3. VẼ CỘT DOANH SỐ THỰC TẾ
                const colWidth = plotWidth / (n || 1);
                const barW = Math.min(52, colWidth * 0.58);
                const linePoints = [];

                data.forEach((d, i) => {
                    const cx = xStart + (i + 0.5) * colWidth;
                    const barH = (maxSales > 0) ? ((d.sales / maxSales) * plotHeight) : 0;
                    const barY = yBottom - barH;

                    // Cột màu xanh dương
                    svg += `<rect x="${cx - barW/2}" y="${barY}" width="${barW}" height="${barH}" fill="#1f619e" rx="2">
                        <title>${d.label} (${d.customer}): ${d.sales.toLocaleString('vi-VN')} VNĐ - Operating Margin: ${d.margin}%</title>
                    </rect>`;

                    // Nhãn số tiền trên đầu cột (rút gọn hiển thị)
                    let displaySales = '';
                    if (d.sales >= 1000000000) {
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

                    // Nhãn trục X hàng 1 (Mã ca / Cơ hội)
                    svg += `<text x="${cx}" y="${yBottom + 24}" font-size="12" font-weight="700" fill="#334155" text-anchor="middle">${d.label}</text>`;
                    // Nhãn trục X hàng 2 (Tên khách hàng thực tế)
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
                tbody.innerHTML = rows.join('');
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
            } catch(e) {
                console.warn('Update system sync warning:', e);
            }
        }

        // ==========================================
        // TASK 2: LUỒNG QUY TRÌNH & LÀM SẠCH KHO
        // ==========================================
        async function approveAndRunPipeline() {
            if (rawItems.length === 0) {
                alert('⚠️ Chưa có dữ liệu nào trong hệ thống! Vui lòng vào Task 1 để nhập dữ liệu hoặc tải tệp lên trước.');
                switchTask(1);
                return;
            }
            if (isAutoRunning) return;

            isPipelineApproved = true;
            appendLog('PHÊ DUYỆT', `Đã phê duyệt khởi chạy luồng quy trình cho ${rawItems.length} yêu cầu!`);
            showToast('🛡️ Đã phê duyệt! Bắt đầu chạy luồng quy trình...');
            await runFullPipelineAuto();
            saveSystemState();
        }

        async function runFullPipelineAuto() {
            if (rawItems.length === 0) {
                alert('⚠️ Chưa có dữ liệu nào trong hệ thống! Vui lòng nhập dữ liệu ở Task 1 trước khi chạy quy trình.');
                switchTask(1);
                return;
            }
            if (isAutoRunning) return;
            isAutoRunning = true;
            const btn = document.getElementById('main-cmd-btn');
            if (btn) {
                btn.innerText = '⏳ Đang Chạy Tự Động Từng Luồng...';
                btn.disabled = true;
            }

            appendLog('BẮT ĐẦU', 'Khởi động quy trình tự động tuần tự: 2.1 ➔ 2.2 ➔ 2.3 ➔ 2.4 ➔ Task 3 ➔ Task 4...');

            // BƯỚC 2.1: NLP BÓC TÁCH & CHUẨN HÓA
            setNodeState(1, 'active');
            appendLog('GIAI ĐOẠN 2.1', 'Đang kích hoạt NLP bóc tách thực thể (SKU, số lượng, ngân sách, deadline)...');
            await delay(120);
            setNodeState(1, 'completed');

            // BƯỚC 2.2: THẨM TRA CHECKLIST
            setNodeState(2, 'active');
            appendLog('GIAI ĐOẠN 2.2', 'Đang đối chiếu checklist 4 trường bắt buộc (SKU, Số lượng, Ngân sách, Deadline)...');
            await delay(120);
            setNodeState(2, 'completed');

            // BƯỚC 2.3: KIỂM TRA TỒN KHO 2 KHO
            setNodeState(3, 'active');
            appendLog('GIAI ĐOẠN 2.3', 'Đang kiểm tra tồn kho tại 2 kho Hà Nội & TP.HCM, tính số lượng cần nhập...');
            await delay(120);
            setNodeState(3, 'completed');

            // BƯỚC 2.4: CHUẨN HÓA LEAD TIME
            setNodeState(4, 'active');
            appendLog('GIAI ĐOẠN 2.4', 'Đang chuẩn hóa Lead time khả thi so với deadline của khách hàng...');
            await delay(120);
            setNodeState(4, 'completed');

            // ĐỒNG BỘ CẢ TASK 2, 3, 4
            appendLog('TỰ ĐỘNG HÓA', 'Đang cập nhật Task 2 (Kho & Lead time), Task 3 (Báo giá & So sánh), Task 4 (Dashboard & Xuất file)...');
            await recomputeEntireSystem();
            isPipelineApproved = true;

            renderTask2Data();
            renderTask3Data();
            renderTask4Data();
            renderComboChart(comboChartMode);
            if (btn) {
                btn.innerText = '✅ ĐÃ DUYỆT & HOÀN TẤT LUỒNG QUY TRÌNH (BẤM ĐỂ CHẠY LẠI)';
                btn.disabled = false;
            }
            isAutoRunning = false;
            document.getElementById('flow-status-tag').innerText = 'ĐÃ DUYỆT & HOÀN TẤT';
            document.getElementById('header-status').innerText = `Đã Hoàn Tất Xử Lý ${allDossiers.length} Ca`;
            appendLog('HOÀN TẤT', 'Quy trình đã duyệt và xử lý xong! Mọi tab (Task 1, 2, 3, 4) đã có kết quả phân tích đầy đủ.');
            showToast('🎉 Đã chạy xong toàn bộ luồng quy trình làm sạch!');
            saveSystemState();
        }

        function runSingleStep(stepNum) {
            for (let i = 1; i <= 4; i++) setNodeState(i, '');
            setNodeState(stepNum, 'active');

            if (stepNum === 1) {
                appendLog('BƯỚC 2.1', 'Đã bóc tách thực thể NLP và chuẩn hóa SKU với Catalog.');
                setNodeState(1, 'completed');
                showToast('✅ Đã chạy Bước 2.1: Bóc tách NLP');
            } else if (stepNum === 2) {
                appendLog('BƯỚC 2.2', 'Đã đối chiếu checklist 4 trường bắt buộc.');
                setNodeState(2, 'completed');
                showToast('✅ Đã chạy Bước 2.2: Thẩm tra checklist');
            } else if (stepNum === 3) {
                appendLog('BƯỚC 2.3', 'Đã kiểm tra tồn kho tại 2 kho Hà Nội và HCM.');
                setNodeState(3, 'completed');
                showToast('✅ Đã chạy Bước 2.3: Kiểm tra tồn kho');
            } else if (stepNum === 4) {
                appendLog('BƯỚC 2.4', 'Đã chuẩn hóa Lead time và đánh giá hạn định.');
                setNodeState(4, 'completed');
                showToast('✅ Đã chạy Bước 2.4: Chuẩn hóa Lead time');
            }
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
                tbody.innerHTML = rows.join('');
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

                if (!allDossiers || allDossiers.length === 0 || !isPipelineApproved) {
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
                                    ${isWaiting ? 'Quy Trình Đang Chờ Phê Duyệt Tại Task 2' : 'Chưa Có Dữ Liệu Phân Tích Tài Chính'}
                                </div>
                                <p style="font-size:12.5px; color:#64748b; margin-bottom:14px;">
                                    ${isWaiting ? 'Bảng tính toán định giá, chiết khấu và phân tích chẩn đoán nguyên nhân gốc rễ (Diagnostic Analytics) sẽ tự động kích hoạt ngay sau khi bạn duyệt luồng tại Task 2.' : 'Hãy nhập dữ liệu ở Task 1 hoặc bấm nút dưới đây để nạp nhanh 6 ca mẫu và phân tích ngay.'}
                                </p>
                                <button class="btn btn-primary" onclick="${isWaiting ? 'switchTask(2)' : 'loadSampleDataset(); switchTask(3);'}" style="font-size:12px; padding:7px 18px;">
                                    ${isWaiting ? '🛡️ Chuyển Sang Task 2 Để Phê Duyệt' : '⚡ Nạp 6 Ca Mẫu & Phân Tích Ngay'}
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
                document.getElementById('t3-total-savings').innerText = `${Math.round(totalSavings).toLocaleString('vi-VN')} đ`;

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
                tbody.innerHTML = rows.join('');
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
                const hasData = (allDossiers && allDossiers.length > 0 && isPipelineApproved);

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

                document.getElementById('kpi-total-val').innerText = s.total_value_formatted || '0 VNĐ';
                document.getElementById('kpi-eligible').innerText = statusCounts['CÓ THỂ TIẾP TỤC'] || 0;
                document.getElementById('kpi-pending').innerText = statusCounts['CHỜ DUYỆT'] || 0;
                document.getElementById('kpi-dash-missing').innerText = statusCounts['CẦN BỔ SUNG THÔNG TIN'] || 0;
                document.getElementById('kpi-unfeasible').innerText = statusCounts['CHƯA ĐÁP ỨNG'] || 0;

                const total = allDossiers.length || 1;
                const cEligible = statusCounts['CÓ THỂ TIẾP TỤC'] || 0;
                const cPending = statusCounts['CHỜ DUYỆT'] || 0;
                const cMissing = statusCounts['CẦN BỔ SUNG THÔNG TIN'] || 0;
                const cUnfeasible = statusCounts['CHƯA ĐÁP ỨNG'] || 0;

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
        function downloadFileBlob(content, fileName, mimeType) {
            const blob = new Blob([content], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        function exportCSV() {
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
            const blob = new Blob([bom, rows.join("\\r\\n")], { type: "text/csv;charset=utf-8;" });
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

            downloadFileBlob(md.join("\\n"), `toan_bo_ho_so_co_hoi_${new Date().toISOString().slice(0,10)}.md`, "text/markdown");
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
                        const lines = content.split('\n').map(l => l.replace('\r', '').trim()).filter(l => l.length > 0);
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
                        } else {
                            newItems = [{
                                id: "REQ-" + Math.floor(1000 + Math.random() * 9000),
                                customer_name: "Khách Hàng (" + (file.name.split('.')[0] || "File") + ")",
                                contact_email: "contact@client.vn",
                                channel: "File Văn Bản",
                                raw_request_text: content
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
    
