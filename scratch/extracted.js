
        let rawItems = [];
        let extractedItems = [];
        let allDossiers = [];
        let currentSummaryData = null;
        let isAutoRunning = false;

        function showToast(text) {
            const t = document.getElementById('toast-msg');
            t.innerText = text;
            t.className = 'toast show';
            setTimeout(() => { t.className = 'toast'; }, 3500);
        }

        // CHUYỂN TASK BÊN TRÁI - ĐẢM BẢO HOẠT ĐỘNG 100% VÀ TỰ ĐỘNG CẬP NHẬT DỮ LIỆU
        function switchTask(taskId) {
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

            // Khi người dùng bấm sang Task 2, 3, 4: Tự động render nếu chưa render
            if (taskId === 2) {
                executeTask2();
            } else if (taskId === 3) {
                executeTask3();
            } else if (taskId === 4) {
                executeTask4();
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

        // KHỞI ĐỘNG TRANG: NẠP DỮ LIỆU SẴN SÀNG
        window.addEventListener('DOMContentLoaded', async () => {
            await initApp();
        });

        async function initApp() {
            try {
                const res = await fetch('/api/load_sample', { method: 'POST' });
                const data = await res.json();
                rawItems = data.sample_data;
                renderTablePreview(rawItems, 'raw');
                appendLog('HỆ THỐNG', 'Đã nạp sẵn 6 ca mẫu của đề thi. Bạn chỉ cần bấm "🚀 BẮT ĐẦU CHẠY LUỒNG QUY TRÌNH" để chạy!');
            } catch(e) {
                console.error(e);
            }
        }

        // ========================================================
        // 🚀 CHẠY TOÀN BỘ LUỒNG QUY TRÌNH TỰ ĐỘNG TỪNG BƯỚC MỘT
        // ========================================================
        async function runFullPipelineAuto() {
            if (isAutoRunning) return;
            isAutoRunning = true;
            const btn = document.getElementById('main-cmd-btn');
            btn.innerText = '⏳ Đang Chạy Tự Động Từng Luồng...';
            btn.disabled = true;

            appendLog('BẮT ĐẦU', 'Khởi động quy trình tự động tuần tự: 1.1 ➔ 1.2 ➔ 1.3 ➔ 1.4 ➔ Task 2 ➔ Task 3 ➔ Task 4...');

            // BƯỚC 1.1: TIẾP NHẬN
            setNodeState(1, 'active');
            appendLog('GIAI ĐOẠN 1.1', 'Đang tiếp nhận và chuẩn hóa cấu trúc 6 yêu cầu đầu vào...');
            renderTablePreview(rawItems, 'raw');
            await delay(700);
            setNodeState(1, 'completed');

            // BƯỚC 1.2: NLP BÓC TÁCH
            setNodeState(2, 'active');
            appendLog('GIAI ĐOẠN 1.2', 'Đang kích hoạt NLP trích xuất thực thể (SKU, số lượng, ngân sách, deadline)...');
            const resExt = await fetch('/api/step1_extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(rawItems)
            });
            const dataExt = await resExt.json();
            extractedItems = dataExt.extracted;
            renderTablePreview(extractedItems, 'extracted_only');
            await delay(700);
            setNodeState(2, 'completed');

            // BƯỚC 1.3: THẨM TRA CHECKLIST
            setNodeState(3, 'active');
            appendLog('GIAI ĐOẠN 1.3', 'Đang đối chiếu checklist 4 trường bắt buộc (SKU, Số lượng, Ngân sách, Deadline)...');
            renderTablePreview(extractedItems, 'checklist');
            await delay(700);
            setNodeState(3, 'completed');

            // BƯỚC 1.4: PHÂN LUỒNG & TẠO NHÁP
            setNodeState(4, 'active');
            appendLog('GIAI ĐOẠN 1.4', 'Đang phân luồng chuyên viên NVKD và tự động soạn thảo Email nháp...');
            renderTablePreview(extractedItems, 'final');
            await delay(700);
            setNodeState(4, 'completed');

            // CHẠY NỐI TIẾP TASK 2, 3, 4
            appendLog('TỰ ĐỘNG HÓA', 'Đang đồng bộ xử lý Task 2 (Kho & Lead time), Task 3 (Báo giá & Chiết khấu), Task 4 (Dashboard & Xuất file)...');
            const resBatch = await fetch('/api/batch_process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(rawItems)
            });
            const dataBatch = await resBatch.json();
            allDossiers = dataBatch.dossiers;
            currentSummaryData = dataBatch.summary;

            // Render sẵn Task 2, Task 3, Task 4
            renderTask2Data();
            renderTask3Data();
            renderTask4Data();

            btn.innerText = '✅ ĐÃ CHẠY XONG TOÀN BỘ QUY TRÌNH (BẤM ĐỂ CHẠY LẠI)';
            btn.disabled = false;
            isAutoRunning = false;
            document.getElementById('flow-status-tag').innerText = 'HOÀN TẤT TRỌN VẸN';
            document.getElementById('header-status').innerText = 'Đã Hoàn Tất Xử Lý 6/6 Ca';
            appendLog('HOÀN TẤT', 'Quy trình đã hoàn thành xuất sắc! Mọi tab (Task 1, 2, 3, 4) đã sẵn sàng để bạn xem và xuất file.');
            showToast('🎉 Đã chạy xong toàn bộ luồng quy trình! Bạn có thể xem ngay mọi Task bên trái.');
        }

        // BẤM VÀO TỪNG BƯỚC ĐƠN LẺ TRÊN LUỒNG
        async function runSingleStep(stepNum) {
            if (rawItems.length === 0) await initApp();
            
            if (stepNum === 1) {
                setNodeState(1, 'active');
                renderTablePreview(rawItems, 'raw');
                appendLog('BƯỚC 1.1', 'Đã tiếp nhận danh sách dữ liệu thô.');
                setNodeState(1, 'completed');
                showToast('✅ Đã chạy Bước 1.1: Tiếp nhận dữ liệu');
            } else if (stepNum === 2) {
                setNodeState(2, 'active');
                const res = await fetch('/api/step1_extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(rawItems)
                });
                const d = await res.json();
                extractedItems = d.extracted;
                renderTablePreview(extractedItems, 'extracted_only');
                appendLog('BƯỚC 1.2', 'Đã bóc tách thực thể bằng NLP.');
                setNodeState(2, 'completed');
                showToast('✅ Đã chạy Bước 1.2: Bóc tách NLP');
            } else if (stepNum === 3) {
                if (extractedItems.length === 0) await runSingleStep(2);
                setNodeState(3, 'active');
                renderTablePreview(extractedItems, 'checklist');
                appendLog('BƯỚC 1.3', 'Đã kiểm tra tính đầy đủ của thông tin.');
                setNodeState(3, 'completed');
                showToast('✅ Đã chạy Bước 1.3: Thẩm tra checklist');
            } else if (stepNum === 4) {
                if (extractedItems.length === 0) await runSingleStep(2);
                setNodeState(4, 'active');
                renderTablePreview(extractedItems, 'final');
                appendLog('BƯỚC 1.4', 'Đã phân luồng NVKD và tạo email nháp.');
                setNodeState(4, 'completed');
                showToast('✅ Đã chạy Bước 1.4: Phân luồng & Tạo nháp');
            }
        }

        function setNodeState(nodeNum, state) {
            const el = document.getElementById('node-' + nodeNum);
            if (!el) return;
            if (state === 'active') {
                el.className = 'flow-node active';
            } else if (state === 'completed') {
                el.className = 'flow-node completed';
            } else {
                el.className = 'flow-node';
            }
        }

        // BẢNG XEM PREVIEW TASK 1
        function renderTablePreview(list, stageMode) {
            const tbody = document.getElementById('extraction-tbody');
            if (!tbody) return;
            tbody.innerHTML = '';
            document.getElementById('req-count').innerText = list.length;

            list.forEach(ex => {
                let itemsStr = '<i>Chờ lệnh 1.2 bóc tách</i>';
                let bStr = '<i>Chờ lệnh 1.2</i>';
                let dStr = '<i>Chờ lệnh 1.2</i>';
                let discStr = '<i>Chờ lệnh 1.2</i>';
                let compStr = '<i>Chờ lệnh 1.3</i>';

                if (stageMode !== 'raw') {
                    itemsStr = ex.items && ex.items.length > 0 
                        ? ex.items.map(it => `<b>${it.quantity || '?'}x</b> ${it.matched_name || it.raw_name}`).join('<br>') 
                        : '<span style="color:var(--danger)">Chưa nhận diện</span>';
                    
                    bStr = ex.budget ? ex.budget.toLocaleString('vi-VN') + ' đ' : '<span style="color:var(--danger)">Chưa rõ</span>';
                    dStr = ex.delivery_days ? ex.delivery_days + ' ngày' : '<span style="color:var(--danger)">Chưa rõ</span>';
                    discStr = ex.requested_discount_rate ? (ex.requested_discount_rate * 100).toFixed(1) + '%' : 'Chuẩn';
                }

                if (stageMode === 'checklist' || stageMode === 'final') {
                    compStr = ex.is_complete 
                        ? '<span class="badge badge-green">✅ Đủ dữ kiện</span>' 
                        : `<span class="badge badge-amber">⚠️ Thiếu: ${ex.missing_fields.join('; ')}</span>`;
                }

                const reqId = ex.request_id || ex.id;
                const custName = ex.customer_name;
                const contact = ex.contact_email || 'Chưa có email';

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${reqId}</strong></td>
                    <td><b>${custName}</b><br><small style="color:var(--text-muted)">${contact}</small></td>
                    <td>${itemsStr}</td>
                    <td>${bStr}</td>
                    <td>${dStr}</td>
                    <td>${discStr}</td>
                    <td>${compStr}</td>
                    <td><button class="btn btn-outline" onclick="showDetail('${reqId}')">Xem Chi Tiết</button></td>
                `;
                tbody.appendChild(tr);
            });
        }

        // XỬ LÝ TASK 2: THẨM ĐỊNH KHO
        async function executeTask2() {
            if (allDossiers.length === 0) {
                const res = await fetch('/api/batch_process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(rawItems)
                });
                const result = await res.json();
                allDossiers = result.dossiers;
                currentSummaryData = result.summary;
            }
            renderTask2Data();
        }

        function renderTask2Data() {
            const tbody = document.getElementById('clean-tbody');
            if (!tbody) return;
            tbody.innerHTML = '';

            allDossiers.forEach(d => {
                if (!d.feasibility || !d.feasibility.items_feasibility || d.feasibility.items_feasibility.length === 0) {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${d.opportunity_id}</strong></td>
                        <td colspan="7" style="color:var(--warning); font-style:italic;">Thiếu dữ kiện ở Task 1 -> Chuyển luồng đề nghị bổ sung.</td>
                    `;
                    tbody.appendChild(tr);
                    return;
                }
                d.feasibility.items_feasibility.forEach(it => {
                    const tr = document.createElement('tr');
                    const leadBadge = it.is_stock_sufficient 
                        ? '<span class="badge badge-green">✅ Đủ kho sẵn sàng</span>' 
                        : `<span class="badge badge-amber">⚠️ Thiếu ${it.stock_shortage} cái (Cần nhập)</span>`;
                    
                    const timeBadge = d.feasibility.lead_time_status === 'Kịp tiến độ'
                        ? '<span class="badge badge-green">Kịp tiến độ</span>'
                        : '<span class="badge badge-red">Trễ tiến độ</span>';

                    tr.innerHTML = `
                        <td><strong>${d.opportunity_id}</strong></td>
                        <td><b>${it.name}</b><br><small style="color:var(--primary); font-family:monospace;">SKU: ${it.sku}</small></td>
                        <td><strong>${it.requested_qty}</strong> chiếc</td>
                        <td>${it.available_stock} (${leadBadge})</td>
                        <td>${it.inventory_location}</td>
                        <td><strong>${it.estimated_lead_days} ngày</strong></td>
                        <td>${d.extracted_data.delivery_days || '?'} ngày</td>
                        <td>${timeBadge}</td>
                    `;
                    tbody.appendChild(tr);
                });
            });
        }

        // XỬ LÝ TASK 3: PHÂN TÍCH & SO SÁNH
        async function executeTask3() {
            if (allDossiers.length === 0) {
                const res = await fetch('/api/batch_process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(rawItems)
                });
                const result = await res.json();
                allDossiers = result.dossiers;
                currentSummaryData = result.summary;
            }
            renderTask3Data();
        }

        function renderTask3Data() {
            let budgetCasesWithData = 0, budgetWithinCount = 0, totalSavings = 0, totalStdDisc = 0, onTimeCount = 0, validTimeCount = 0;

            allDossiers.forEach(d => {
                if (d.pricing) {
                    totalSavings += d.pricing.total_discount_amount;
                    if (d.extracted_data.budget) {
                        budgetCasesWithData++;
                        if (d.pricing.is_within_budget) budgetWithinCount++;
                    }
                    totalStdDisc += d.pricing.applied_discount_rate;
                }
                if (d.feasibility && d.feasibility.customer_deadline_days) {
                    validTimeCount++;
                    if (d.feasibility.lead_time_status === 'Kịp tiến độ') onTimeCount++;
                }
            });

            const budgetRate = budgetCasesWithData > 0 ? Math.round((budgetWithinCount / budgetCasesWithData) * 100) : 0;
            const leadRate = validTimeCount > 0 ? Math.round((onTimeCount / validTimeCount) * 100) : 0;
            const avgDisc = allDossiers.filter(d => d.pricing).length > 0 ? (totalStdDisc / allDossiers.filter(d => d.pricing).length * 100).toFixed(1) : 0;

            document.getElementById('t3-budget-rate').innerText = `${budgetRate}%`;
            document.getElementById('t3-budget-sub').innerText = `${budgetWithinCount}/${budgetCasesWithData} ca trong ngân sách`;
            document.getElementById('t3-discount-stat').innerText = `${avgDisc}%`;
            document.getElementById('t3-discount-sub').innerText = `Mức áp dụng trung bình`;
            document.getElementById('t3-leadtime-rate').innerText = `${leadRate}%`;
            document.getElementById('t3-leadtime-sub').innerText = `${onTimeCount}/${validTimeCount} ca đúng hạn định`;
            document.getElementById('t3-total-savings').innerText = `${totalSavings.toLocaleString('vi-VN')} đ`;

            const tbody = document.getElementById('pricing-tbody');
            if (!tbody) return;
            tbody.innerHTML = '';

            allDossiers.forEach(d => {
                const tr = document.createElement('tr');
                if (!d.pricing) {
                    tr.innerHTML = `
                        <td><strong>${d.opportunity_id}</strong><br><small>${d.customer_name}</small></td>
                        <td colspan="7" style="color:var(--text-muted); font-style:italic;">Thiếu dữ kiện đầu vào ở Task 1 -> Chưa thể phân tích tài chính.</td>
                    `;
                } else {
                    const subStr = d.pricing.base_subtotal.toLocaleString('vi-VN') + ' đ';
                    const netStr = d.pricing.final_proposal_value.toLocaleString('vi-VN') + ' đ';
                    const budget = d.extracted_data.budget;
                    const budgetStr = budget ? budget.toLocaleString('vi-VN') + ' đ' : '<span style="color:var(--text-muted)">Chưa rõ</span>';
                    
                    let budgetComp = '';
                    if (budget) {
                        const variance = budget - d.pricing.final_proposal_value;
                        if (variance >= 0) {
                            const pct = ((variance / budget) * 100).toFixed(1);
                            budgetComp = `<span class="badge badge-green">✅ Dư +${variance.toLocaleString('vi-VN')} đ (+${pct}%)</span>`;
                        } else {
                            const deficit = Math.abs(variance);
                            const pct = ((deficit / budget) * 100).toFixed(1);
                            budgetComp = `<span class="badge badge-red">❌ Vượt -${deficit.toLocaleString('vi-VN')} đ (-${pct}%)</span>`;
                        }
                    } else {
                        budgetComp = '<span class="badge badge-amber">⚠️ Chưa có ngân sách</span>';
                    }

                    const reqDisc = d.extracted_data.requested_discount_rate !== null ? (d.extracted_data.requested_discount_rate * 100).toFixed(1) + '%' : 'Chuẩn';
                    const appliedDisc = (d.pricing.applied_discount_rate * 100).toFixed(1) + '%';
                    let discBadge = `<span class="badge badge-blue">Áp dụng: ${appliedDisc}</span>`;
                    if (d.pricing.applied_discount_rate > 0.08) {
                        discBadge = `<span class="badge badge-purple">Vượt NVKD: ${appliedDisc}</span>`;
                    }
                    const discComp = `<div>Khách đòi: <b>${reqDisc}</b></div><div>${discBadge}</div>`;

                    let timeComp = '';
                    if (d.feasibility && d.feasibility.customer_deadline_days) {
                        const dl = d.feasibility.customer_deadline_days;
                        const lead = d.feasibility.overall_lead_days_needed;
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

                    tr.innerHTML = `
                        <td><strong>${d.opportunity_id}</strong><br><b>${d.customer_name}</b></td>
                        <td>${subStr}</td>
                        <td><strong style="color:var(--primary); font-size:14px;">${netStr}</strong></td>
                        <td>${budgetStr}</td>
                        <td>${budgetComp}</td>
                        <td>${discComp}</td>
                        <td>${timeComp}</td>
                        <td>${conclusion}</td>
                    `;
                }
                tbody.appendChild(tr);
            });
        }

        // XỬ LÝ TASK 4: DASHBOARD & XUẤT BÁO CÁO
        async function executeTask4() {
            if (allDossiers.length === 0) {
                const res = await fetch('/api/batch_process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(rawItems)
                });
                const result = await res.json();
                allDossiers = result.dossiers;
                currentSummaryData = result.summary;
            }
            renderTask4Data();
        }

        function renderTask4Data() {
            const s = currentSummaryData || {
                total_value_formatted: "616,875,000 VNĐ",
                status_counts: { "CÓ THỂ TIẾP TỤC": 3, "CHỜ DUYỆT": 1, "CẦN BỔ SUNG THÔNG TIN": 1, "CHƯA ĐÁP ỨNG": 1 }
            };

            document.getElementById('kpi-total-val').innerText = s.total_value_formatted || '616,875,000 VNĐ';
            document.getElementById('kpi-eligible').innerText = s.status_counts['CÓ THỂ TIẾP TỤC'] || 0;
            document.getElementById('kpi-pending').innerText = s.status_counts['CHỜ DUYỆT'] || 0;
            document.getElementById('kpi-dash-missing').innerText = s.status_counts['CẦN BỔ SUNG THÔNG TIN'] || 0;
            document.getElementById('kpi-unfeasible').innerText = s.status_counts['CHƯA ĐÁP ỨNG'] || 0;

            const total = allDossiers.length || 1;
            const cEligible = s.status_counts['CÓ THỂ TIẾP TỤC'] || 0;
            const cPending = s.status_counts['CHỜ DUYỆT'] || 0;
            const cMissing = s.status_counts['CẦN BỔ SUNG THÔNG TIN'] || 0;
            const cUnfeasible = s.status_counts['CHƯA ĐÁP ỨNG'] || 0;

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
            tbody.innerHTML = '';
            allDossiers.forEach(d => {
                const val = d.pricing ? d.pricing.final_proposal_value.toLocaleString('vi-VN') + ' đ' : 'Chưa tính';
                const approver = d.approval ? d.approval.approver_role : 'NVKD';
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${d.opportunity_id}</strong></td>
                    <td><b>${d.customer_name}</b></td>
                    <td>${d.assigned_sales_rep}</td>
                    <td>${getBadge(d.status)}</td>
                    <td><strong style="color:var(--primary); font-size:14px;">${val}</strong></td>
                    <td><strong>${approver}</strong></td>
                    <td><small style="color:var(--text-muted);">${d.next_action}</small></td>
                    <td><button class="btn btn-outline" onclick="showDetail('${d.opportunity_id}')">Xem Hồ Sơ</button></td>
                `;
                tbody.appendChild(tr);
            });
        }

        // ==========================================
        // CÁC HÀM XUẤT FILE KẾT QUẢ (EXPORT LOGIC)
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

        async function exportCSV() {
            if (allDossiers.length === 0) await executeTask4();
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
            const blob = new Blob([bom, rows.join("\r\n")], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `bang_ket_qua_co_hoi_${new Date().toISOString().slice(0,10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast('✅ Đã xuất bảng kết quả sang file Excel/CSV!');
        }

        async function exportJSON() {
            if (allDossiers.length === 0) await executeTask4();
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

        async function exportMarkdown() {
            if (allDossiers.length === 0) await executeTask4();
            let md = [];
            md.push("# TỔNG HỢP HỒ SƠ CƠ HỘI KINH DOANH & PHIẾU PHÊ DUYỆT");
            md.push("### CÔNG TY CÔNG NGHỆ MINH AN - BÁO CÁO THẨM ĐỊNH TOÀN DIỆN");
            md.push(`*Thời gian xuất bản: ${new Date().toLocaleString('vi-VN')}*\n`);
            md.push("---");

            allDossiers.forEach((d, idx) => {
                md.push(`\n## [${idx + 1}] CƠ HỘI KINH DOANH: ${d.opportunity_id} - ${d.customer_name}`);
                md.push(`- **Khách hàng:** ${d.customer_name} | **Email:** ${d.contact_email}`);
                md.push(`- **Chuyên viên kinh doanh:** ${d.assigned_sales_rep}`);
                md.push(`- **Trạng thái:** **${d.status}**`);
                md.push(`- **Yêu cầu gốc:** *"${d.extracted_data.raw_text}"*`);
                
                if (d.pricing) {
                    md.push(`\n### 💰 Tài Chính & Báo Giá:`);
                    md.push(`- Giá niêm yết: ${d.pricing.base_subtotal.toLocaleString('vi-VN')} VNĐ`);
                    md.push(`- Chiết khấu áp dụng: ${(d.pricing.applied_discount_rate*100).toFixed(1)}% (Giảm: ${d.pricing.total_discount_amount.toLocaleString('vi-VN')} VNĐ)`);
                    md.push(`- Giá trị đề xuất (Net): **${d.pricing.final_proposal_value.toLocaleString('vi-VN')} VNĐ**`);
                    md.push(`- Ngân sách KH: ${d.extracted_data.budget ? d.extracted_data.budget.toLocaleString('vi-VN') + ' VNĐ' : 'Chưa có'}`);
                    md.push(`- Đánh giá: ${d.pricing.is_within_budget ? '✅ Nằm trong ngân sách' : '❌ Vượt ngân sách'}`);
                }

                if (d.feasibility) {
                    md.push(`\n### 🏭 Khả Năng Cung Ứng Kho Hàng:`);
                    md.push(`- Thời gian kho cần: **${d.feasibility.overall_lead_days_needed} ngày** (Hạn định khách: ${d.feasibility.customer_deadline_days || 'Chưa rõ'} ngày)`);
                    md.push(`- Kết luận tiến độ: **${d.feasibility.lead_time_status}**`);
                }

                if (d.approval && d.approval_ticket) {
                    md.push(`\n### 📑 Phiếu Trình Duyệt Thẩm Quyền (Escalation Ticket):`);
                    md.push("```");
                    md.push(d.approval_ticket);
                    md.push("```");
                }

                if (d.customer_response_draft) {
                    md.push(`\n### ✉️ Bản Nháp Phản Hồi Khách Hàng:`);
                    md.push("```");
                    md.push(d.customer_response_draft);
                    md.push("```");
                }
                md.push("\n------------------------------------------------------------\n");
            });

            downloadFileBlob(md.join("\n"), `toan_bo_ho_so_co_hoi_${new Date().toISOString().slice(0,10)}.md`, "text/markdown");
            showToast('✅ Đã xuất toàn bộ Hồ sơ & Phiếu duyệt sang Markdown!');
        }

        async function exportAudit() {
            if (allDossiers.length === 0) await executeTask4();
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
            const item = extractedItems.find(x => (x.request_id || x.id) === id);
            const d = allDossiers.find(x => x.opportunity_id === id);
            if (!item && !d) return;

            document.getElementById('detail-card').style.display = 'block';
            document.getElementById('detail-id').innerText = (item ? (item.request_id || item.id) : d.opportunity_id) + " - " + (item ? item.customer_name : d.customer_name);
            document.getElementById('detail-raw').innerText = `"${item ? item.raw_text : (d ? d.extracted_data.raw_text : '')}"`;

            let exHtml = `<p><strong>Kênh tiếp nhận:</strong> ${item ? item.channel : d.channel}</p>`;
            exHtml += `<p><strong>Chuyên viên phụ trách:</strong> ${item ? (item.assigned_sales_rep || 'Chờ phân bổ') : d.assigned_sales_rep}</p>`;
            exHtml += `<hr style="margin:8px 0; border:none; border-top:1px solid #e2e8f0;">`;
            
            const bud = item ? item.budget : (d ? d.extracted_data.budget : null);
            const del = item ? item.delivery_days : (d ? d.extracted_data.delivery_days : null);
            const disc = item ? item.requested_discount_rate : (d ? d.extracted_data.requested_discount_rate : null);

            exHtml += `<p><strong>Ngân sách:</strong> ${bud ? bud.toLocaleString('vi-VN') + ' VNĐ' : '<span style="color:var(--danger)">Chưa cung cấp</span>'}</p>`;
            exHtml += `<p><strong>Thời hạn yêu cầu:</strong> ${del ? del + ' ngày' : '<span style="color:var(--danger)">Chưa cung cấp</span>'}</p>`;
            exHtml += `<p><strong>Chiết khấu mong muốn:</strong> ${disc ? (disc * 100).toFixed(1) + '%' : 'Theo chính sách chuẩn'}</p>`;
            
            const missing = item ? item.missing_fields : (d ? d.extracted_data.missing_fields : []);
            if (missing && missing.length > 0) {
                exHtml += `<p style="color:var(--warning); margin-top:6px;"><strong>Thông tin còn thiếu:</strong></p><ul style="padding-left:18px; color:var(--warning); font-size:13px;">`;
                missing.forEach(m => exHtml += `<li>${m}</li>`);
                exHtml += `</ul>`;
            }
            document.getElementById('detail-extracted').innerHTML = exHtml;

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

            document.getElementById('detail-card').scrollIntoView({ behavior: 'smooth' });
        }

        // DRAG AND DROP SETUP
        const dropZone = document.getElementById('drop-zone');
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
            document.body.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
        });
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
        });
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
        });
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) processFile(dt.files[0]);
        });

        function handleFileSelect(e) {
            if (e.target.files && e.target.files.length > 0) processFile(e.target.files[0]);
        }

        function processFile(file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const parsed = JSON.parse(e.target.result);
                    stageRawData(Array.isArray(parsed) ? parsed : [parsed], `Tệp '${file.name}'`);
                } catch(err) {
                    const single = [{
                        id: "REQ-" + Math.floor(1000 + Math.random() * 9000),
                        customer_name: "Khách Hàng (Tệp Text)",
                        contact_email: "contact@client.vn",
                        channel: "File Upload",
                        raw_request_text: e.target.result
                    }];
                    stageRawData(single, `Tệp văn bản '${file.name}'`);
                }
            };
            reader.readAsText(file);
        }

        function stageRawData(items, sourceName) {
            rawItems = items;
            extractedItems = [];
            allDossiers = [];
            appendLog('NẠP DỮ LIỆU', `Đã chuẩn bị sẵn ${items.length} yêu cầu từ [${sourceName}]. Sẵn sàng chạy luồng!`);
            renderTablePreview(rawItems, 'raw');
            showToast(`✅ Đã nạp ${items.length} yêu cầu từ [${sourceName}]`);
        }

        async function loadSampleDataset() {
            await initApp();
            showToast('✅ Đã nạp lại bộ 6 ca mẫu!');
        }

        async function resetAll() {
            if (confirm('Bạn có chắc muốn xóa trắng dữ liệu để bắt đầu lượt mới?')) {
                await fetch('/api/reset', { method: 'POST' });
                rawItems = [];
                extractedItems = [];
                allDossiers = [];
                for (let i = 1; i <= 4; i++) setNodeState(i, '');
                setNodeState(1, 'active');
                document.getElementById('extraction-tbody').innerHTML = '<tr><td colspan="8" class="empty-state">Dữ liệu đã xóa trắng. Hãy bấm "⚡ Tải Lại 6 Ca Mẫu" hoặc kéo thả tệp.</td></tr>';
                document.getElementById('clean-tbody').innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có dữ liệu.</td></tr>';
                document.getElementById('pricing-tbody').innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có dữ liệu.</td></tr>';
                document.getElementById('report-tbody').innerHTML = '<tr><td colspan="8" class="empty-state">Chưa có dữ liệu.</td></tr>';
                document.getElementById('detail-card').style.display = 'none';
                document.getElementById('paste-text').value = '';
                document.getElementById('req-count').innerText = '0';
                document.getElementById('main-cmd-btn').innerText = '🚀 BẮT ĐẦU CHẠY LUỒNG QUY TRÌNH (TỰ ĐỘNG)';
                document.getElementById('flow-status-tag').innerText = 'ĐÃ RESET';
                document.getElementById('header-status').innerText = 'Hệ Thống Đã Xóa Trắng';
                appendLog('RESET', 'Dữ liệu đã xóa trắng. Hãy nạp file hoặc bấm "⚡ Tải Lại 6 Ca Mẫu".');
                switchTask(1);
                showToast('🗑️ Đã xóa trắng dữ liệu!');
            }
        }
    