
        // ── State ──────────────────────────────────────────────────────────────────
        let BASE_URL = localStorage.getItem('dms_url') || '';
        let currentPage = 1;
        let totalPages = 1;
        let autoTimer = null;
        let searchTimer = null;

        // Image Viewer State
        let currentRecordId = null;
        let zoomLevel = 1;
        let panX = 0;
        let panY = 0;
        let isPanning = false;
        let startPanX = 0;
        let startPanY = 0;

        // ── Init ───────────────────────────────────────────────────────────────────
        document.addEventListener('DOMContentLoaded', () => {
            if (BASE_URL) {
                document.getElementById('serverUrl').value = BASE_URL;
                loadAll();
            }

            // Try to set username from cookie or a simple API call if available
            // Since we can't reliably read the flask session from JS, leaving as Admin
            // The API doesn't expose a /me endpoint in the python code.
        });

        // ── Server config ──────────────────────────────────────────────────────────
        function applyServer() {
            const raw = document.getElementById('serverUrl').value.trim().replace(/\/$/, '');
            if (!raw) return;
            BASE_URL = raw;
            localStorage.setItem('dms_url', BASE_URL);
            currentPage = 1;
            loadAll();
        }

        // ── Load everything ────────────────────────────────────────────────────────
        async function loadAll() {
            if (!BASE_URL) return;
            document.getElementById('refreshRing').classList.add('active');
            await Promise.all([loadStats(), loadData()]);
            document.getElementById('refreshRing').classList.remove('active');
        }

        // ── Number Animation ───────────────────────────────────────────────────────
        function animateValue(obj, start, end, duration) {
            let startTimestamp = null;
            const step = (timestamp) => {
                if (!startTimestamp) startTimestamp = timestamp;
                const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                const current = Math.floor(progress * (end - start) + start);
                obj.innerHTML = current.toLocaleString();
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                } else {
                    obj.innerHTML = end.toLocaleString();
                }
            };
            window.requestAnimationFrame(step);
        }

        function updateStatWithAnimation(id, newValue) {
            const el = document.getElementById(id);
            const oldVal = parseInt(el.getAttribute('data-val') || '0', 10);
            const newVal = parseFloat(newValue) || 0;
            if (oldVal !== newVal && !isNaN(newVal)) {
                animateValue(el, oldVal, newVal, 500);
                el.setAttribute('data-val', newVal);
            } else if (isNaN(newVal)) {
                el.textContent = newValue; // strings or float formats
            }
        }

        // ── Stats ──────────────────────────────────────────────────────────────────
        async function loadStats() {
            try {
                const r = await fetch(`${BASE_URL}/stats`);
                if (r.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                const d = await r.json();
                if (d.status !== 'ok') return;

                updateStatWithAnimation('sTotalRecords', d.total_records);
                updateStatWithAnimation('sUniqueSensors', d.unique_sensors);
                updateStatWithAnimation('sWorkOrders', d.unique_work_orders);
                updateStatWithAnimation('sAvgQuality', d.avg_quality);
                updateStatWithAnimation('sAvgNfiq', d.avg_nfiq);

                if (d.last_received) {
                    const dt = new Date(d.last_received);
                    document.getElementById('sLastReceived').textContent = dt.toLocaleTimeString();
                    document.getElementById('sLastReceivedSub').textContent = dt.toLocaleDateString();
                }
                setStatus('online', 'Connected');
            } catch {
                setStatus('offline', 'Unreachable');
            }
        }

        // ── Data table ─────────────────────────────────────────────────────────────
        async function loadData() {
            if (!BASE_URL) return;
            const search = document.getElementById('searchInput').value.trim();
            const perPage = parseInt(document.getElementById('perPageSelect').value);
            const params = new URLSearchParams({ page: currentPage, per_page: perPage });
            if (search) params.set('search', search);

            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = `<tr><td colspan="11">
                <div class="empty-state"><div class="spinner"></div></div>
            </td></tr>`;

            try {
                const r = await fetch(`${BASE_URL}/data?${params}`);
                if (r.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                const d = await r.json();
                if (d.status !== 'ok') throw new Error(d.message);

                const total = d.total;
                totalPages = Math.max(1, Math.ceil(total / perPage));
                document.getElementById('totalCount').textContent = total.toLocaleString();
                document.getElementById('showingCount').textContent = d.rows.length.toLocaleString();

                if (d.rows.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="11"><div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                        <div class="title">No records found</div></div></td></tr>`;
                    document.getElementById('pagination').style.display = 'none';
                    return;
                }

                tbody.innerHTML = d.rows.map(row => `
                    <tr>
                        <td class="mono">${esc(row.sensor_sn)}</td>
                        <td><span class="badge badge-blue">${esc(row.model)}</span></td>
                        <td class="mono" style="color:var(--muted)">${esc(row.sensor_mac)}</td>
                        <td>${scoreBar(row.quality_score_afiq, 100, true)}</td>
                        <td>${scoreBar(row.nfiq_score, 100, false)}</td>
                        <td style="text-align:right" class="mono">${row.minutiae_count}</td>
                        <td>${scoreBar(row.verification_score, 500, true)}</td>
                        <td class="mono">${esc(row.work_order)}</td>
                        <td><span class="badge badge-green">${esc(row.tester_id)}</span></td>
                        <td style="color:var(--text-secondary)">${fmtDate(row.received_at)}</td>
                        <td class="actions-cell">
                            <button class="btn-icon btn-icon-primary tooltip" data-tooltip="Preview Fingerprint" onclick="openPreviewModal(event, ${escJson(row)})" onmouseenter="showHoverPreview(event, ${escJson(row)})" onmouseleave="hideHoverPreview(event)">
                                <svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                            </button>
                            <button class="btn-icon btn-icon-success tooltip" data-tooltip="Download JSON" onclick="downloadRowJson(event, ${escJson(row)})">
                                <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                            </button>
                        </td>
                    </tr>
                `).join('');

                renderPagination(total, perPage);
                document.getElementById('pagination').style.display = totalPages > 1 ? 'flex' : 'none';

            } catch (e) {
                tbody.innerHTML = `<tr><td colspan="11"><div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                    <div class="title">Error Loading Data</div>
                    <div>${esc(e.message || 'Failed to load data')}</div></div></td></tr>`;
            }
        }

        // ── Helpers ────────────────────────────────────────────────────────────────
        function esc(s) {
            return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }
        function escJson(obj) {
            return "'" + JSON.stringify(obj).replace(/'/g, "\\'") + "'";
        }
        function fmtDate(iso) {
            if (!iso) return '—';
            const d = new Date(iso);
            return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
        }
        function scoreBar(val, max, isSuccess) {
            const pct = Math.min(100, Math.round((val / max) * 100));
            const fillClass = isSuccess ? 'score-bar-fill success' : 'score-bar-fill';
            return `<div class="score-bar-wrap">
                <span class="score-bar-val mono">${val}</span>
                <div class="score-bar"><div class="${fillClass}" style="width:${pct}%"></div></div>
            </div>`;
        }
        function setStatus(state, text) {
            const dot = document.getElementById('statusDot');
            dot.className = 'status-dot ' + state;
            document.getElementById('statusText').textContent = text;
        }

        // ── Pagination ─────────────────────────────────────────────────────────────
        function renderPagination(total, perPage) {
            const pg = document.getElementById('pagination');
            const pages = Math.ceil(total / perPage);

            let html = `<div class="page-info">Page ${currentPage} of ${pages}</div><div class="pagination-controls">`;
            html += `<button class="page-btn" onclick="gotoPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg>
            </button>`;

            const range = pageRange(currentPage, pages);
            let prev = null;
            for (const p of range) {
                if (prev !== null && p - prev > 1) html += `<span class="page-info">…</span>`;
                html += `<button class="page-btn ${p === currentPage ? 'active' : ''}" onclick="gotoPage(${p})">${p}</button>`;
                prev = p;
            }
            html += `<button class="page-btn" onclick="gotoPage(${currentPage + 1})" ${currentPage === pages ? 'disabled' : ''}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </button></div>`;
            pg.innerHTML = html;
        }
        function pageRange(cur, total) {
            const delta = 2, range = [], rangeWithDots = [];
            for (let i = Math.max(2, cur - delta); i <= Math.min(total - 1, cur + delta); i++) range.push(i);
            if (range[0] - 1 > 1) range.unshift('...');
            else range.unshift(1);
            if (total - range[range.length - 1] > 1) range.push('...');
            range.push(total);
            const seen = new Set();
            for (const p of range) { if (p !== '...' && !seen.has(p)) { seen.add(p); rangeWithDots.push(p); } }
            return rangeWithDots.filter(p => p !== '...' && p >= 1 && p <= total);
        }
        function gotoPage(p) {
            if (p < 1 || p > totalPages) return;
            currentPage = p;
            loadData();
        }
        function perPageChanged() { currentPage = 1; loadData(); }

        // ── Search ─────────────────────────────────────────────────────────────────
        function debouncedSearch() {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => { currentPage = 1; loadData(); }, 350);
        }

        // ── Auto-refresh ───────────────────────────────────────────────────────────
        function toggleAutoRefresh() {
            const btn = document.getElementById('autoBtn');
            if (autoTimer) {
                clearInterval(autoTimer);
                autoTimer = null;
                btn.innerHTML = 'Auto-refresh: OFF';
                btn.className = 'btn btn-secondary';
            } else {
                autoTimer = setInterval(loadAll, 10000);
                btn.innerHTML = 'Auto-refresh: ON (10s)';
                btn.className = 'btn btn-secondary';
                btn.style.color = 'var(--accent)';
                btn.style.borderColor = 'var(--accent)';
                loadAll();
            }
        }
        // ── Hover Preview Panel ────────────────────────────────────────────────────
        const imageCache = new Map();
        let hoverShowTimer = null;
        let hoverHideTimer = null;
        let activeHoverRow = null;

        function showHoverPreview(event, rowJson) {
            clearTimeout(hoverHideTimer);

            const btn = event.currentTarget;
            const row = typeof rowJson === 'string' ? JSON.parse(rowJson) : rowJson;

            hoverShowTimer = setTimeout(() => {
                activeHoverRow = row;
                const panel = document.getElementById('hoverPreviewPanel');

                // Render info grid
                const fields = [
                    ['Sensor SN', row.sensor_sn],
                    ['Model', row.model],
                    ['MAC', row.sensor_mac],
                    ['Work Order', row.work_order],
                    ['Tester', row.tester_id],
                    ['AFIQ', row.quality_score_afiq],
                    ['NFIQ', row.nfiq_score],
                    ['Verify', row.verification_score],
                    ['Minutiae', row.minutiae_count],
                    ['Format', row.image_format || 'N/A'],
                ];

                document.getElementById('hoverDeviceInfoGrid').innerHTML = fields.map(([k, v]) =>
                    `<div class="info-card">
                        <div class="info-label">${esc(k)}</div>
                        <div class="info-value">${esc(v ?? '—')}</div>
                    </div>`
                ).join('');

                // Load Image using Map Cache
                const imgEl = document.getElementById('hoverPreviewImage');
                const skelEl = document.getElementById('hoverImageSkeleton');
                imgEl.classList.remove('loaded');
                imgEl.src = '';

                const imgSrc = `${BASE_URL}/image/${row.id}`;

                if (imageCache.has(row.id)) {
                    // Already cached
                    skelEl.style.display = 'none';
                    imgEl.src = imageCache.get(row.id);
                    imgEl.classList.add('loaded');
                } else {
                    skelEl.style.display = 'block';
                    const tempImg = new Image();
                    tempImg.onload = () => {
                        imageCache.set(row.id, imgSrc);
                        // Only update if we're still hovering over the same record
                        if (activeHoverRow && activeHoverRow.id === row.id) {
                            skelEl.style.display = 'none';
                            imgEl.src = imgSrc;
                            // small delay to ensure rendering before fading in
                            setTimeout(() => imgEl.classList.add('loaded'), 50);
                        }
                    };
                    tempImg.onerror = () => {
                        skelEl.style.display = 'none';
                    };
                    tempImg.src = imgSrc;
                }

                // Smart Positioning
                const rect = btn.getBoundingClientRect();
                // Panel is 420px wide. Place it to the left of the button by default
                let left = rect.left - 420 - 16;
                let top = rect.top - 60; // offset slightly up

                // If it overflows on the left, show it on the right
                if (left < 16) {
                    left = rect.right + btn.offsetWidth + 16;
                }

                // If it overflows on the bottom, push it up
                // We'll estimate height at 500px, but it will adjust
                if (top + 500 > window.innerHeight) {
                    top = Math.max(16, window.innerHeight - 520);
                }

                panel.style.left = left + 'px';
                // Because panel is position: absolute on body, we add window.scrollY
                panel.style.top = top + window.scrollY + 'px';
                panel.classList.add('open');
            }, 200);
        }

        function hideHoverPreview(event) {
            clearTimeout(hoverShowTimer);
            hoverHideTimer = setTimeout(() => {
                document.getElementById('hoverPreviewPanel').classList.remove('open');
                activeHoverRow = null;
            }, 200);
        }

        function keepHoverPreview() {
            clearTimeout(hoverHideTimer);
        }

        function openFullFromHover() {
            hideHoverPreview();
            if (activeHoverRow) {
                openPreviewModal(null, activeHoverRow);
            }
        }

        function downloadImageFromHover() {
            if (activeHoverRow) {
                window.location.href = `${BASE_URL}/download/${activeHoverRow.id}`;
            }
        }


        // ── Right Side Image Preview Panel ─────────────────────────────────────────
        function openPreviewModal(event, rowJson) {
            if (event) event.stopPropagation();
            const row = typeof rowJson === 'string' ? JSON.parse(rowJson) : rowJson;
            currentRecordId = row.id;

            // Populate Device Info Grid
            const fields = [
                ['Sensor SN', row.sensor_sn, false],
                ['Model', row.model, false],
                ['Work Order', row.work_order, false],
                ['Tester', row.tester_id, false],
                ['AFIQ', row.quality_score_afiq, false],
                ['NFIQ', row.nfiq_score, false],
                ['Verify Score', row.verification_score, false],
                ['Client IP', row.client_ip, false],
                ['Received Time', fmtDate(row.received_at), true],
            ];

            document.getElementById('deviceInfoGrid').innerHTML = fields.map(([k, v, full]) =>
                `<div class="info-card ${full ? 'full' : ''}">
                    <div class="info-label">${esc(k)}</div>
                    <div class="info-value">${esc(v ?? '—')}</div>
                </div>`
            ).join('');

            // Load Image
            resetZoom();
            document.getElementById('imageSkeleton').style.display = 'block';
            document.getElementById('imgResolution').textContent = 'Loading...';

            const imgEl = document.getElementById('previewImage');
            imgEl.classList.remove('loaded');
            // Provide a conceptual standard REST route for the image retrieval
            imgEl.src = `${BASE_URL}/image/${row.id}`;

            document.getElementById('previewBackdrop').classList.add('open');
            document.getElementById('previewPanel').classList.add('open');
        }

        function closePreviewModal(e) {
            if (!e || e.target === document.getElementById('previewBackdrop') || e.target.closest('.panel-close')) {
                document.getElementById('previewBackdrop').classList.remove('open');
                document.getElementById('previewPanel').classList.remove('open');
                setTimeout(() => {
                    document.getElementById('previewImage').src = '';
                }, 350);
            }
        }

        // ── Image Viewer Logic ─────────────────────────────────────────────────────
        function imageLoaded() {
            document.getElementById('imageSkeleton').style.display = 'none';
            const img = document.getElementById('previewImage');
            img.classList.add('loaded');
            document.getElementById('imgResolution').textContent = `${img.naturalWidth} x ${img.naturalHeight}px`;
        }

        function imageError() {
            document.getElementById('imageSkeleton').style.display = 'none';
            document.getElementById('imgResolution').textContent = 'Image Unavailable';
            // Optional: set a placeholder src here
        }

        function handleZoom(e) {
            e.preventDefault();
            const zoomStep = 0.1;
            if (e.deltaY < 0) manualZoom(zoomStep);
            else manualZoom(-zoomStep);
        }

        function manualZoom(delta) {
            zoomLevel += delta;
            zoomLevel = Math.max(0.5, Math.min(zoomLevel, 5));
            applyTransform();
        }

        function startPan(e) {
            e.preventDefault();
            isPanning = true;
            startPanX = e.clientX - panX;
            startPanY = e.clientY - panY;
        }

        function doPan(e) {
            if (!isPanning) return;
            e.preventDefault();
            panX = e.clientX - startPanX;
            panY = e.clientY - startPanY;
            applyTransform();
        }

        function endPan() {
            isPanning = false;
        }

        function resetZoom() {
            zoomLevel = 1;
            panX = 0;
            panY = 0;
            applyTransform();
        }

        function applyTransform() {
            const img = document.getElementById('previewImage');
            img.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
        }

        function toggleFullscreen() {
            document.getElementById('previewPanel').classList.toggle('fullscreen');
        }

        function downloadCurrentImage() {
            if (currentRecordId) {
                window.open(`${BASE_URL}/download/${currentRecordId}`, '_blank');
            }
        }

        function openOriginalImage() {
            if (currentRecordId) {
                window.open(`${BASE_URL}/image/${currentRecordId}`, '_blank');
            }
        }

        // Action button download JSON
        function downloadRowJson(e, rowJson) {
            e.stopPropagation();
            const row = typeof rowJson === 'string' ? JSON.parse(rowJson) : rowJson;
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(row, null, 2));
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", dataStr);
            downloadAnchorNode.setAttribute("download", `record_${row.sensor_sn}.json`);
            document.body.appendChild(downloadAnchorNode);
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        }

        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') closePreviewModal();
        });

        async function handleLogout() {
            try {
                const response = await fetch(`${BASE_URL}/logout`, { method: 'POST' });
                if (response.ok) {
                    window.location.href = '/login';
                }
            } catch (err) {
                console.error("Logout failed", err);
            }
        }
    