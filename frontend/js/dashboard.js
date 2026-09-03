/**
 * Dashboard & Negotiation UI Controller
 * AI Negotiator — An Autonomous B2B Wholesale Negotiation Platform
 */

// ── App State ──
let currentUser = null;
let currentPage = 'dashboard';
let currentNegotiationId = null;

// ── Simple label helper (English-only UI with Urdu headings in HTML) ──
function t(key) {
    const labels = {
        below_mandi: 'below mandi (good deal!)',
        above_mandi: 'above mandi',
        mandi_comparison: '📊 Mandi Rate Comparison',
        mandi_rate: 'Mandi Rate:',
        deal_price: 'Deal Price:',
        approve_deal: '✅ Approve Deal',
        reject_deal: '❌ Reject & Continue',
        approval_needed: 'Approval Needed',
        contract_generated: 'Contract Generated',
    };
    return labels[key] || key;
}

// ── Supplier Cache (loaded once, reused for dropdowns) ──
let _cachedSuppliers = [];

async function loadSupplierCache() {
    try {
        _cachedSuppliers = await API.listSuppliers();
        if (!_cachedSuppliers.length) {
            await API.seedSuppliers();
            _cachedSuppliers = await API.listSuppliers();
        }
    } catch (e) {
        console.error('Failed to load supplier cache:', e);
    }
}

/** Populate the single-form supplier dropdown, optionally filtered by commodity */
function populateSupplierDropdown(commodity) {
    const sel = document.getElementById('neg_supplier_select');
    if (!sel) return;
    const filtered = commodity
        ? _cachedSuppliers.filter(s => s.commodity && s.commodity.toLowerCase().includes(commodity.toLowerCase()))
        : _cachedSuppliers;
    sel.innerHTML = '<option value="">— Choose a supplier (auto-fills name, phone, price) —</option>';
    filtered.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = `${s.supplier_name} — ${s.commodity} — ${s.city || ''} ${s.whatsapp_number ? '(' + s.whatsapp_number + ')' : ''}`;
        sel.appendChild(opt);
    });
    // Add "Custom" option
    const customOpt = document.createElement('option');
    customOpt.value = '__custom__';
    customOpt.textContent = '✏️ Custom / Not listed (type manually)';
    sel.appendChild(customOpt);
}

/** Called when user picks a supplier from the dropdown */
function onSupplierSelected(supplierId) {
    const infoBar = document.getElementById('neg_supplier_info_bar');
    const infoText = document.getElementById('neg_supplier_info_text');
    if (!supplierId || supplierId === '__custom__') {
        // Clear auto-filled fields for manual entry
        if (supplierId === '__custom__') {
            document.getElementById('neg_seller_name').value = '';
            document.getElementById('neg_seller_whatsapp').value = '';
            document.getElementById('neg_seller_start').value = '';
            document.getElementById('neg_seller_min').value = '';
            document.getElementById('neg_seller_name').focus();
        }
        if (infoBar) infoBar.style.display = 'none';
        return;
    }
    const supplier = _cachedSuppliers.find(s => s.id === supplierId);
    if (!supplier) return;

    // Auto-fill fields
    document.getElementById('neg_seller_name').value = supplier.supplier_name || '';
    document.getElementById('neg_seller_whatsapp').value = supplier.whatsapp_number || '';
    if (supplier.price) {
        document.getElementById('neg_seller_start').value = supplier.price;
        document.getElementById('neg_seller_min').value = Math.round(supplier.price * 0.85);
    }
    // Show supplier info bar
    if (infoBar && infoText) {
        infoBar.style.display = 'block';
        const parts = [];
        if (supplier.business_type) parts.push(`📋 ${supplier.business_type}`);
        if (supplier.city) parts.push(`📍 ${supplier.city}`);
        if (supplier.whatsapp_number) parts.push(`📱 ${supplier.whatsapp_number}`);
        if (supplier.supplier_rating) parts.push(`⭐ ${supplier.supplier_rating}`);
        if (supplier.minimum_order_quantity) parts.push(`MOQ: ${supplier.minimum_order_quantity.toLocaleString()} ${supplier.unit}`);
        infoText.textContent = parts.join('  •  ');
    }
}

// ── Mandi Notice Helper ──
async function updateMandiNotice(commodityId, noticeId) {
    const commodity = document.getElementById(commodityId)?.value;
    const noticeText = document.getElementById(noticeId);
    if (!commodity || !noticeText) return;
    noticeText.innerHTML = 'Fetching mandi rate...';
    try {
        const rate = await API.getMarketRate(commodity);
        if (rate && rate.rate_per_kg) {
            const low = Math.round(rate.rate_per_kg * 0.85);
            const high = Math.round(rate.rate_per_kg * 1.15);
            noticeText.innerHTML = `
                <span class="mandi-notice-rate">${commodity}: PKR ${rate.rate_per_kg.toLocaleString()}/kg</span>
                <span class="mandi-notice-range">
                    Suggested price range: <strong>PKR ${low.toLocaleString()} \u2013 ${high.toLocaleString()}/kg</strong>
                    &nbsp;\u2022&nbsp; Source: ${rate.source}
                    &nbsp;\u2022&nbsp; Use this as a reference when setting your buyer & seller prices.
                </span>
            `;
        }
    } catch (e) {
        noticeText.innerHTML = `No mandi data available for ${commodity}. Enter rates manually below.`;
    }
}

// ── Initialize ──
document.addEventListener('DOMContentLoaded', () => {
    // Auto-fetch mandi rate when commodity changes (single form)
    document.getElementById('neg_commodity')?.addEventListener('change', () => {
        autoFetchMandiRate('neg_commodity', 'neg_mandi_rate', 'mandi_hint');
        updateMandiNotice('neg_commodity', 'mandi_notice_single_text');
        populateSupplierDropdown(document.getElementById('neg_commodity').value);
    });

    // Auto-fetch mandi rate when commodity changes (batch form)
    document.getElementById('batch_commodity')?.addEventListener('change', () => {
        updateMandiNotice('batch_commodity', 'mandi_notice_batch_text');
        refreshBatchSellerDropdowns();
    });

    // Load supplier cache on app start
    loadSupplierCache();

    // Trigger initial mandi notice for default commodity
    setTimeout(() => {
        updateMandiNotice('neg_commodity', 'mandi_notice_single_text');
        updateMandiNotice('batch_commodity', 'mandi_notice_batch_text');
    }, 500);

    if (API.token) {
        API.getMe().then(user => {
            currentUser = user;
            showApp();
            loadDashboard();
        }).catch(() => showLogin());
    } else {
        showLogin();
    }
});

// ── Auth UI ──
function showLogin() {
    document.getElementById('loginPage').classList.remove('hidden');
    document.getElementById('appLayout').classList.add('hidden');
}

function showApp() {
    document.getElementById('loginPage').classList.add('hidden');
    document.getElementById('appLayout').classList.remove('hidden');
    document.getElementById('userName').textContent = currentUser?.full_name || 'User';
    document.getElementById('userOrg').textContent = currentUser?.organization_id?.slice(0, 8) || '';
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    try {
        await API.login(email, password);
        currentUser = await API.getMe();
        showApp();
        loadDashboard();
    } catch (err) {
        alert('Login failed: ' + err.message);
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const data = {
        email: document.getElementById('regEmail').value,
        password: document.getElementById('regPassword').value,
        full_name: document.getElementById('regName').value,
        organization_name: document.getElementById('regOrg').value,
    };
    try {
        await API.register(data);
        await API.login(data.email, data.password);
        currentUser = await API.getMe();
        showApp();
        loadDashboard();
    } catch (err) {
        alert('Registration failed: ' + err.message);
    }
}

function toggleAuthForm() {
    const login = document.getElementById('loginForm');
    const reg = document.getElementById('registerForm');
    login.classList.toggle('hidden');
    reg.classList.toggle('hidden');
}

// ── Navigation ──
function navigate(page) {
    currentPage = page;
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`[data-page="${page}"]`)?.classList.add('active');
    document.querySelectorAll('.page-section').forEach(el => el.classList.add('hidden'));
    document.getElementById(`page-${page}`)?.classList.remove('hidden');

    if (page === 'dashboard') loadDashboard();
    if (page === 'negotiations') loadNegotiations();
    if (page === 'suppliers') loadSuppliers();
    if (page === 'contracts') loadContracts();
    if (page === 'batch') loadBatches();
}

// ── Dashboard ──
async function loadDashboard() {
    try {
        const stats = await API.getStats();
        document.getElementById('statActive').textContent = stats.active_negotiations;
        document.getElementById('statCompleted').textContent = stats.completed_deals;
        document.getElementById('statTerminated').textContent = stats.terminated_negotiations;
        document.getElementById('statValue').textContent =
            `${stats.total_negotiated_value.toLocaleString()} PKR`;
        document.getElementById('statAvgRounds').textContent = stats.average_rounds;
        document.getElementById('statAgreementRate').textContent = `${stats.agreement_rate}%`;
    } catch (err) {
        console.error('Failed to load dashboard:', err);
    }
}

// ── Negotiations List ──
async function loadNegotiations() {
    try {
        const negs = await API.listNegotiations();
        const tbody = document.getElementById('negotiationsTable');
        tbody.innerHTML = negs.map(n => `
            <tr onclick="viewNegotiation('${n.id}')" style="cursor:pointer">
                <td>${n.commodity}</td>
                <td>${n.quantity.toLocaleString()} ${n.unit}</td>
                <td>${n.currency} ${n.final_price ? n.final_price.toLocaleString() : '—'}</td>
                <td>Round ${n.current_round}</td>
                <td><span class="badge badge-${n.status.toLowerCase()}">${n.status.replace(/_/g, ' ')}</span></td>
                <td>${new Date(n.created_at).toLocaleDateString()}</td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Failed to load negotiations:', err);
    }
}

// ── Create Negotiation ──
function openCreateModal() {
    document.getElementById('createModal').classList.add('active');
    switchModalTab('single');  // always open on single-seller tab
    // Populate supplier dropdown with current commodity
    populateSupplierDropdown(document.getElementById('neg_commodity')?.value);
    // Reset supplier selection
    const sel = document.getElementById('neg_supplier_select');
    if (sel) sel.value = '';
    const infoBar = document.getElementById('neg_supplier_info_bar');
    if (infoBar) infoBar.style.display = 'none';
}

function openBatchModal() {
    document.getElementById('createModal').classList.add('active');
    switchModalTab('batch');   // open directly on batch tab
    // Clear and re-add seller rows with updated supplier dropdown
    const container = document.getElementById('sellerRowsContainer');
    container.innerHTML = '';
    _sellerRowCount = 0;
    addSellerRow();
    addSellerRow();
}

function closeCreateModal() {
    document.getElementById('createModal').classList.remove('active');
}

// Toggle between Single Seller and Batch tabs
function switchModalTab(tab) {
    const fSingle = document.getElementById('formSingle');
    const fBatch  = document.getElementById('formBatch');
    const tSingle = document.getElementById('tabSingle');
    const tBatch  = document.getElementById('tabBatch');
    if (tab === 'single') {
        fSingle.classList.remove('hidden');
        fBatch.classList.add('hidden');
        tSingle.style.background = 'var(--primary)';
        tSingle.style.color = '#fff';
        tBatch.style.background = 'var(--bg-card)';
        tBatch.style.color = 'var(--text-muted)';
    } else {
        fBatch.classList.remove('hidden');
        fSingle.classList.add('hidden');
        tBatch.style.background = 'var(--primary)';
        tBatch.style.color = '#fff';
        tSingle.style.background = 'var(--bg-card)';
        tSingle.style.color = 'var(--text-muted)';
        // Initialise with 2 seller rows if empty
        const container = document.getElementById('sellerRowsContainer');
        if (!container.children.length) {
            addSellerRow();
            addSellerRow();
        }
    }
    // Always populate supplier dropdowns
    populateSupplierDropdown(document.getElementById('neg_commodity')?.value);
}

async function handleCreateNegotiation(e) {
    e.preventDefault();

    try {
        const sellerStart = parseFloat(document.getElementById('neg_seller_start').value) || null;
        const sellerMin   = parseFloat(document.getElementById('neg_seller_min').value) || null;
        const mandiRate   = parseFloat(document.getElementById('neg_mandi_rate').value) || null;
        const approvalMode = document.getElementById('neg_approval_mode').value || 'HUMAN_APPROVAL';

        const data = {
            commodity: document.getElementById('neg_commodity').value,
            quantity: parseFloat(document.getElementById('neg_quantity').value),
            unit: document.getElementById('neg_unit').value,
            currency: document.getElementById('neg_currency')?.value || 'PKR',
            buyer_starting_price: parseFloat(document.getElementById('neg_buyer_start').value),
            buyer_reservation_price: parseFloat(document.getElementById('neg_buyer_max').value),
            buyer_delivery_days: parseInt(document.getElementById('neg_buyer_delivery').value),
            buyer_payment_terms: document.getElementById('neg_buyer_payment').value,
            buyer_strategy: document.getElementById('neg_buyer_strategy').value,
            buyer_max_rounds: parseInt(document.getElementById('neg_max_rounds').value),
            seller_name: document.getElementById('neg_seller_name')?.value?.trim() || null,
            seller_whatsapp: document.getElementById('neg_seller_whatsapp')?.value?.trim() || null,
            seller_starting_price: sellerStart,
            seller_reservation_price: sellerMin,
            seller_delivery_days: 21,
            seller_strategy: 'BALANCED',
            mandi_rate: mandiRate,
            convergence_mode: 'MIDPOINT',
            approval_mode: approvalMode,
        };

        // Validate
        if (!data.commodity || !data.quantity || !data.buyer_starting_price || !data.buyer_reservation_price) {
            alert('Please fill in all required fields.');
            return;
        }
        if (data.buyer_reservation_price <= data.buyer_starting_price) {
            alert('Buyer max price must be higher than starting price.');
            return;
        }

        closeCreateModal();

        // Show loading state
        const btn = e.target.querySelector('button[type="submit"]');
        const origText = btn?.textContent;
        if (btn) { btn.textContent = 'Running AI Negotiation...'; btn.disabled = true; }

        const neg = await API.createNegotiation(data);
        await API.startNegotiation(neg.id);
        const result = await API.runFull(neg.id);

        if (btn) { btn.textContent = origText; btn.disabled = false; }

        viewNegotiation(neg.id);
    } catch (err) {
        console.error('Create negotiation error:', err);
        alert('Failed to create negotiation: ' + err.message);
        const btn = e.target.querySelector('button[type="submit"]');
        if (btn) { btn.disabled = false; }
    }
}

// ── View Negotiation Detail ──
async function viewNegotiation(id) {
    currentNegotiationId = id;
    navigate('negotiation-detail');
    try {
        const [neg, offers, status] = await Promise.all([
            API.getNegotiation(id),
            API.getOffers(id),
            API.getNegotiationStatus(id),
        ]);

        document.getElementById('detail_commodity').textContent = neg.commodity;
        document.getElementById('detail_status').innerHTML =
            `<span class="badge badge-${neg.status.toLowerCase()}">${neg.status.replace('_', ' ')}</span>`;
        document.getElementById('detail_quantity').textContent = `${neg.quantity.toLocaleString()} ${neg.unit}`;
        document.getElementById('detail_rounds').textContent = `${neg.current_round} / ${neg.buyer_max_rounds}`;
        document.getElementById('detail_final').textContent =
            neg.final_price ? `${neg.currency} ${neg.final_price.toLocaleString()}` : 'Pending';

        // Mandi rate stat card
        if (neg.mandi_rate && neg.mandi_rate > 0) {
            document.getElementById('detail_mandi_rate').textContent =
                `${neg.currency} ${neg.mandi_rate.toLocaleString()}/kg`;
            // Show mandi comparison bar
            const mandiBar = document.getElementById('mandiBar');
            mandiBar.classList.remove('hidden');
            document.getElementById('bar_mandi_rate').textContent =
                `${neg.currency} ${neg.mandi_rate.toLocaleString()}/kg`;
            if (neg.final_price) {
                document.getElementById('bar_deal_price').textContent =
                    `${neg.currency} ${neg.final_price.toLocaleString()}/unit`;
                const diff = neg.final_price - neg.mandi_rate;
                const pct = ((diff / neg.mandi_rate) * 100).toFixed(1);
                const savingsEl = document.getElementById('bar_mandi_savings');
                if (diff <= 0) {
                    savingsEl.innerHTML = `<span style="color:var(--success);font-weight:700">\u25BC ${Math.abs(pct)}% ${t('below_mandi')}</span>`;
                } else {
                    savingsEl.innerHTML = `<span style="color:var(--danger);font-weight:700">\u25B2 +${pct}% ${t('above_mandi')}</span>`;
                }
            } else {
                document.getElementById('bar_deal_price').textContent = 'Pending';
                document.getElementById('bar_mandi_savings').innerHTML = '';
            }
        } else {
            document.getElementById('detail_mandi_rate').textContent = 'N/A';
            document.getElementById('mandiBar').classList.add('hidden');
        }

        // Render offers timeline & chart (wrapped to not block modal logic)
        try {
            renderTimeline(offers);
            renderChart(offers, neg);
        } catch (renderErr) {
            console.warn('Chart/timeline render error (non-fatal):', renderErr);
        }

        // ── Modals & notifications: hide all first, then show the correct one ──
        console.log('[viewNegotiation] status =', neg.status, '| final_price =', neg.final_price);
        document.getElementById('approvalModal').classList.remove('active');
        document.getElementById('sellerNotification').classList.add('hidden');

        if (neg.status === 'HUMAN_APPROVAL') {
            showApprovalModal(neg);
        }

        if (neg.status === 'SELLER_APPROVAL') {
            showSellerNotification(neg);
        }

        // Load contract if agreed
        if (neg.status === 'AGREED') {
            try {
                const contract = await API.getContract(id);
                document.getElementById('contractSection').classList.remove('hidden');
                document.getElementById('contract_value').textContent =
                    `${contract.currency} ${contract.total_value.toLocaleString()}`;
                document.getElementById('contract_price').textContent =
                    `${contract.currency} ${contract.unit_price}/unit`;
                document.getElementById('contract_hash').textContent =
                    contract.document_hash?.slice(0, 32) + '...';

                // Mandi comparison
                if (neg.mandi_rate && neg.mandi_rate > 0) {
                    const mandiDiv = document.getElementById('mandiComparison');
                    mandiDiv.classList.remove('hidden');
                    document.getElementById('mandi_rate_display').textContent =
                        `${neg.currency} ${neg.mandi_rate.toLocaleString()}/kg`;
                    document.getElementById('deal_price_display').textContent =
                        `${neg.currency} ${neg.final_price.toLocaleString()}/kg`;
                    const diff = neg.final_price - neg.mandi_rate;
                    const pct = ((diff / neg.mandi_rate) * 100).toFixed(1);
                    const savingsEl = document.getElementById('mandi_savings');
                    if (diff <= 0) {
                        savingsEl.innerHTML = `<span style="color:var(--success);font-weight:700">${Math.abs(pct)}% ${t('below_mandi')}</span>`;
                    } else {
                        savingsEl.innerHTML = `<span style="color:var(--danger);font-weight:700">+${pct}% ${t('above_mandi')}</span>`;
                    }
                } else {
                    document.getElementById('mandiComparison').classList.add('hidden');
                }
            } catch (e) { /* no contract yet */ }
        } else {
            document.getElementById('contractSection').classList.add('hidden');
        }
    } catch (err) {
        console.error('Failed to load negotiation:', err);
    }
}

// ── Timeline ──
function renderTimeline(offers) {
    const container = document.getElementById('negotiationTimeline');
    if (!offers.length) {
        container.innerHTML = '<p class="text-muted">No offers yet.</p>';
        return;
    }

    container.innerHTML = offers.map(o => `
        <div class="timeline-item">
            <div class="timeline-dot ${o.sender.toLowerCase()}">
                ${o.sender === 'BUYER' ? '🛒' : '📦'}
            </div>
            <div class="timeline-content">
                <div class="round-label">Round ${o.round_number} — ${o.sender} — ${o.action}</div>
                <div class="price">${o.offer_price.toLocaleString()} PKR/${o.delivery_days ? 'unit' : 'unit'}</div>
                <div class="rationale">${o.public_rationale || ''}</div>
                ${o.validation_result !== 'VALID' ? `<div class="text-danger" style="font-size:12px;margin-top:4px">${o.validation_result}</div>` : ''}
            </div>
        </div>
    `).join('');
}

// ── Chart ──
function renderChart(offers, neg) {
    const canvas = document.getElementById('negotiationChart');
    if (!canvas || !offers.length) return;

    const buyerOffers = offers.filter(o => o.sender === 'BUYER').map(o => o.offer_price);
    const sellerOffers = offers.filter(o => o.sender === 'SELLER').map(o => o.offer_price);
    const labels = offers.filter(o => o.sender === 'BUYER').map(o => `R${o.round_number}`);

    // Simple canvas chart (no external dependency needed)
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.parentElement.clientWidth - 48;
    const H = canvas.height = 250;
    ctx.clearRect(0, 0, W, H);

    const allPrices = [...buyerOffers, ...sellerOffers];
    if (!allPrices.length) return;
    const minP = Math.min(...allPrices) * 0.95;
    const maxP = Math.max(...allPrices) * 1.05;
    const range = maxP - minP || 1;

    const xStep = W / Math.max(labels.length - 1, 1);

    function drawLine(data, color) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        data.forEach((v, i) => {
            const x = i * xStep + 40;
            const y = H - 30 - ((v - minP) / range) * (H - 60);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Draw dots
        data.forEach((v, i) => {
            const x = i * xStep + 40;
            const y = H - 30 - ((v - minP) / range) * (H - 60);
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fill();
            // Price label
            ctx.fillStyle = '#E8E9ED';
            ctx.font = '11px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(v.toFixed(0), x, y - 12);
        });
    }

    // Grid
    ctx.strokeStyle = '#2D3348';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
        const y = 30 + (i / 4) * (H - 60);
        ctx.beginPath();
        ctx.moveTo(40, y);
        ctx.lineTo(W, y);
        ctx.stroke();
        ctx.fillStyle = '#8B92A5';
        ctx.font = '10px Inter';
        ctx.textAlign = 'right';
        ctx.fillText((maxP - (i / 4) * range).toFixed(0), 35, y + 4);
    }

    // Round labels
    labels.forEach((l, i) => {
        ctx.fillStyle = '#8B92A5';
        ctx.font = '11px Inter';
        ctx.textAlign = 'center';
        ctx.fillText(l, i * xStep + 40, H - 8);
    });

    drawLine(buyerOffers, '#2196F3');
    drawLine(sellerOffers, '#FF6A00');

    // Legend
    ctx.fillStyle = '#2196F3';
    ctx.fillRect(W - 200, 10, 12, 12);
    ctx.fillStyle = '#E8E9ED';
    ctx.font = '12px Inter';
    ctx.textAlign = 'left';
    ctx.fillText('Buyer', W - 182, 20);

    ctx.fillStyle = '#FF6A00';
    ctx.fillRect(W - 120, 10, 12, 12);
    ctx.fillStyle = '#E8E9ED';
    ctx.fillText('Seller', W - 102, 20);

    // Final price line
    if (neg.final_price) {
        const y = H - 30 - ((neg.final_price - minP) / range) * (H - 60);
        ctx.strokeStyle = '#00C853';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(40, y);
        ctx.lineTo(W, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#00C853';
        ctx.font = 'bold 12px Inter';
        ctx.textAlign = 'left';
        ctx.fillText(`AGREED: ${neg.final_price}`, 44, y - 6);
    }

    // Mandi rate reference line
    if (neg.mandi_rate && neg.mandi_rate > 0) {
        const yM = H - 30 - ((neg.mandi_rate - minP) / range) * (H - 60);
        if (yM > 30 && yM < H - 30) {
            ctx.strokeStyle = '#FFD600';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(40, yM);
            ctx.lineTo(W, yM);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.fillStyle = '#FFD600';
            ctx.font = 'bold 11px Inter';
            ctx.textAlign = 'right';
            ctx.fillText(`MANDI: ${neg.mandi_rate}`, W - 10, yM - 5);
        }
    }
}

// ── Suppliers ──
async function loadSuppliers() {
    try {
        const suppliers = await API.listSuppliers();
        if (!suppliers.length) {
            // Auto-seed
            await API.seedSuppliers();
            return loadSuppliers();
        }
        // Update cache
        _cachedSuppliers = suppliers;
        const tbody = document.getElementById('suppliersTable');
        tbody.innerHTML = suppliers.map(s => `
            <tr>
                <td><strong>${s.supplier_name}</strong></td>
                <td>${s.commodity}</td>
                <td>${s.business_type || '—'}</td>
                <td>${s.city || '—'}</td>
                <td>${s.currency} ${s.price?.toLocaleString() || '—'}</td>
                <td style="font-family:monospace;font-size:12px">${s.whatsapp_number || '—'}</td>
                <td>${s.minimum_order_quantity?.toLocaleString() || '—'} ${s.unit}</td>
                <td>${s.supplier_rating ? '⭐ ' + s.supplier_rating : '—'}</td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Failed to load suppliers:', err);
    }
}

// ── Contracts ──
async function loadContracts() {
    try {
        const negs = await API.listNegotiations();
        const agreed = negs.filter(n => n.status === 'AGREED');
        const tbody = document.getElementById('contractsTable');
        if (!agreed.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align:center;padding:40px">No contracts yet. Complete a negotiation to generate one.</td></tr>';
            return;
        }
        tbody.innerHTML = agreed.map(n => `
            <tr>
                <td onclick="viewNegotiation('${n.id}')" style="cursor:pointer">${n.commodity}</td>
                <td onclick="viewNegotiation('${n.id}')" style="cursor:pointer">${n.quantity.toLocaleString()} ${n.unit}</td>
                <td onclick="viewNegotiation('${n.id}')" style="cursor:pointer">${n.currency} ${n.final_price?.toLocaleString() || '—'}</td>
                <td onclick="viewNegotiation('${n.id}')" style="cursor:pointer">${n.currency} ${(n.final_price * n.quantity).toLocaleString()}</td>
                <td><span class="badge badge-agreed">GENERATED</span></td>
                <td>${new Date(n.created_at).toLocaleDateString()}</td>
                <td>
                    <button onclick="event.stopPropagation(); viewContractById('${n.id}')" style="padding:6px 14px;background:var(--primary);color:#fff;border:none;border-radius:4px;font-size:12px;font-weight:600;cursor:pointer;margin-right:4px">View</button>
                    <button onclick="event.stopPropagation(); printContractById('${n.id}')" style="padding:6px 14px;background:var(--success);color:#fff;border:none;border-radius:4px;font-size:12px;font-weight:600;cursor:pointer">Print</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Failed to load contracts:', err);
    }
}

// ── Contract Preview / Print / Download ──

async function viewContract() {
    if (!currentNegotiationId) return alert('No negotiation selected.');
    await viewContractById(currentNegotiationId);
}

async function viewContractById(negId) {
    try {
        const html = await API.getContractHTML(negId);
        const win = window.open('', '_blank');
        if (!win) return alert('Please allow pop-ups to view the contract.');
        win.document.open();
        win.document.write(html);
        win.document.close();
    } catch (err) {
        console.error('Contract preview error:', err);
        alert('Failed to load contract preview. Please try again.');
    }
}

async function printContract() {
    if (!currentNegotiationId) return alert('No negotiation selected.');
    await printContractById(currentNegotiationId);
}

async function printContractById(negId) {
    try {
        const html = await API.getContractHTML(negId);
        const win = window.open('', '_blank');
        if (!win) return alert('Please allow pop-ups to print the contract.');
        win.document.open();
        win.document.write(html);
        win.document.close();
        // Auto-trigger print dialog after content loads
        win.onload = () => win.print();
    } catch (err) {
        console.error('Print contract error:', err);
        alert('Failed to print contract. Please try again.');
    }
}

async function downloadContractHTML() {
    if (!currentNegotiationId) return alert('No negotiation selected.');
    try {
        const html = await API.getContractHTML(currentNegotiationId);
        const blob = new Blob([html], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `contract-${currentNegotiationId.slice(0, 8)}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('Download contract error:', err);
        alert('Failed to download contract. Please try again.');
    }
}

// ── WhatsApp Contact ──
async function sendWhatsAppNotification() {
    if (!currentNegotiationId) return alert('No negotiation selected.');
    const btn = document.getElementById('btnWhatsAppContact');
    try {
        if (btn) { btn.textContent = '\u23F3 Sending...'; btn.disabled = true; }
        const result = await API.notifyWhatsApp(currentNegotiationId);

        if (result.status === 'sent') {
            // Production: message was sent via WhatsApp Cloud API
            alert(`\u2705 WhatsApp message sent to ${result.phone}!`);
        } else if (result.status === 'dev_link') {
            // Dev mode: open wa.me deep link
            const confirmed = confirm(
                `WhatsApp API not configured.\n\n` +
                `Click OK to open WhatsApp Web to contact:\n${result.phone}\n\n` +
                `The deal summary has been prepared for you.`
            );
            if (confirmed) {
                // Encode message and open wa.me
                const encoded = encodeURIComponent(result.message);
                window.open(`${result.wa_url}?text=${encoded}`, '_blank');
            }
        }
    } catch (err) {
        console.error('WhatsApp error:', err);
        if (err.message && err.message.includes('No WhatsApp number')) {
            alert('\u26A0\uFE0F No WhatsApp number was saved for this seller.\n\nCreate a new negotiation and enter the seller\'s WhatsApp number.');
        } else {
            alert('WhatsApp notification failed: ' + err.message);
        }
    } finally {
        if (btn) { btn.textContent = '\u{1F4F1} Contact Seller on WhatsApp'; btn.disabled = false; }
    }
}


// ── Human Approval Functions ──

function showApprovalModal(neg) {
    document.getElementById('approval_price').textContent =
        `${neg.currency} ${neg.final_price ? neg.final_price.toLocaleString() : '—'}/unit`;
    document.getElementById('approval_commodity').textContent =
        `${neg.commodity} — ${neg.quantity.toLocaleString()} ${neg.unit} — ${neg.seller_name || 'Seller'}`;

    // Show mandi info if available
    const mandiInfo = document.getElementById('approval_mandi_info');
    if (neg.mandi_rate && neg.mandi_rate > 0 && neg.final_price) {
        mandiInfo.classList.remove('hidden');
        document.getElementById('approval_mandi_rate').textContent =
            `${neg.currency} ${neg.mandi_rate.toLocaleString()}/kg`;
        const diff = neg.final_price - neg.mandi_rate;
        const pct = ((diff / neg.mandi_rate) * 100).toFixed(1);
        const diffEl = document.getElementById('approval_mandi_diff');
        if (diff <= 0) {
            diffEl.innerHTML = `<span style="color:var(--success)">${Math.abs(pct)}% ${t('below_mandi')}</span>`;
        } else {
            diffEl.innerHTML = `<span style="color:var(--danger)">+${pct}% ${t('above_mandi')}</span>`;
        }
    } else {
        mandiInfo.classList.add('hidden');
    }

    document.getElementById('approvalModal').classList.add('active');
}

async function approveCurrentDeal() {
    if (!currentNegotiationId) return;
    const modal = document.getElementById('approvalModal');
    try {
        const btn = modal.querySelector('.btn-success');
        if (btn) { btn.textContent = '\u23F3 Processing...'; btn.disabled = true; }
        const result = await API.approveNegotiation(currentNegotiationId);
        modal.classList.remove('active');
        if (btn) { btn.textContent = '\u2705 Buyer Approves'; btn.disabled = false; }
        // Buyer approved — refresh to show seller notification with link
        viewNegotiation(currentNegotiationId);
    } catch (err) {
        alert('Approval failed: ' + err.message);
        const btn = modal.querySelector('.btn-success');
        if (btn) { btn.textContent = '\u2705 Buyer Approves'; btn.disabled = false; }
    }
}

async function rejectCurrentDeal() {
    if (!currentNegotiationId) return;
    const modal = document.getElementById('approvalModal');
    try {
        const btn = modal.querySelector('.btn-danger');
        if (btn) { btn.textContent = '\u23F3 Processing...'; btn.disabled = true; }
        const result = await API.rejectNegotiation(currentNegotiationId);
        modal.classList.remove('active');
        if (btn) { btn.textContent = '❌ Buyer Rejects'; btn.disabled = false; }

        alert(result.message || 'Deal rejected — negotiation terminated.');
        viewNegotiation(currentNegotiationId);
    } catch (err) {
        alert('Reject failed: ' + err.message);
        const btn = modal.querySelector('.btn-danger');
        if (btn) { btn.textContent = '❌ Buyer Rejects'; btn.disabled = false; }
    }
}

function showSellerNotification(neg) {
    try {
        // Seller contact info
        const contactEl = document.getElementById('seller_notif_contact');
        if (contactEl) {
            if (neg.seller_name) {
                contactEl.textContent = neg.seller_whatsapp
                    ? `${neg.seller_name} (${neg.seller_whatsapp})`
                    : neg.seller_name;
            } else {
                contactEl.textContent = 'Seller (contact not provided)';
            }
        }

        // Build the seller approval link from the token
        const token = neg.seller_approval_token;
        const linkInput = document.getElementById('seller_notif_link');
        if (linkInput && token) {
            linkInput.value = `${window.location.origin}/seller-respond/${token}`;
        } else if (linkInput) {
            linkInput.value = 'Link not available — token was not generated.';
        }

        // Show the notification card
        document.getElementById('sellerNotification').classList.remove('hidden');
    } catch (err) {
        console.error('showSellerNotification error:', err);
    }
}

function copySellerLink() {
    const linkInput = document.getElementById('seller_notif_link');
    if (!linkInput) return;
    linkInput.select();
    navigator.clipboard.writeText(linkInput.value).then(() => {
        const btn = document.getElementById('copyLinkBtn');
        if (btn) {
            btn.textContent = '\u2705 Copied!';
            btn.style.background = '#16a34a';
            setTimeout(() => {
                btn.textContent = '\uD83D\uDCCB Copy';
                btn.style.background = '#22c55e';
            }, 2000);
        }
    });
}

// ── Auto-fetch mandi rate when commodity changes ──
async function autoFetchMandiRate(commodityInputId, mandiInputId, hintId) {
    const commodity = document.getElementById(commodityInputId)?.value;
    const mandiInput = document.getElementById(mandiInputId);
    const hint = hintId ? document.getElementById(hintId) : null;
    if (!commodity || !mandiInput) return;
    try {
        const rate = await API.getMarketRate(commodity);
        if (rate && rate.rate_per_kg) {
            mandiInput.value = rate.rate_per_kg;
            mandiInput.placeholder = `${rate.rate_per_kg} (auto)`;
            if (hint) hint.textContent = `Auto-fetched: ${rate.source}`;
        }
    } catch (e) {
        // Silently fail — user can still enter manually
    }
}

// ══════════════════════════════════════════════════════════
// BATCH NEGOTIATION
// ══════════════════════════════════════════════════════════

let _sellerRowCount = 0;

/** Append a seller input row to the batch form — with supplier dropdown */
function addSellerRow() {
    const container = document.getElementById('sellerRowsContainer');
    if (container.children.length >= 10) {
        alert('Maximum 10 sellers allowed per batch.');
        return;
    }
    const idx = _sellerRowCount++;
    const rowNum = container.children.length + 1;
    const commodity = document.getElementById('batch_commodity')?.value || '';
    const filtered = commodity
        ? _cachedSuppliers.filter(s => s.commodity && s.commodity.toLowerCase().includes(commodity.toLowerCase()))
        : _cachedSuppliers;

    const supplierOptions = filtered.map(s =>
        `<option value="${s.id}">${s.supplier_name} — ${s.city || ''} ${s.whatsapp_number ? '(' + s.whatsapp_number + ')' : ''}</option>`
    ).join('');

    const row = document.createElement('div');
    row.id = `sellerRow_${idx}`;
    row.style.cssText = 'display:flex;gap:10px;align-items:flex-end;margin-bottom:10px;flex-wrap:wrap';
    row.innerHTML = `
        <div class="form-group" style="flex:2;min-width:180px;margin-bottom:0">
            <label style="font-size:12px">Supplier ${rowNum}</label>
            <select class="form-control batch-supplier-select" onchange="onBatchSupplierSelected(this, ${idx})">
                <option value="">— Select supplier —</option>
                ${supplierOptions}
                <option value="__custom__">✏️ Custom</option>
            </select>
        </div>
        <div class="form-group" style="flex:2;min-width:150px;margin-bottom:0">
            <label style="font-size:12px">Name</label>
            <input type="text" class="form-control batch-seller-name" placeholder="e.g. Al-Rehman Traders" required>
        </div>
        <div class="form-group" style="flex:1;min-width:130px;margin-bottom:0">
            <label style="font-size:12px">WhatsApp</label>
            <input type="tel" class="form-control batch-seller-whatsapp" placeholder="+923001234567">
        </div>
        <button type="button" onclick="removeSellerRow('sellerRow_${idx}')"
            style="padding:8px 14px;background:var(--danger);color:#fff;border:none;border-radius:var(--radius-sm);cursor:pointer;font-size:18px;line-height:1;height:38px;margin-bottom:0">&times;</button>
    `;
    container.appendChild(row);
}

/** Auto-fill batch seller row when supplier is selected */
function onBatchSupplierSelected(selectEl, idx) {
    const row = document.getElementById(`sellerRow_${idx}`);
    if (!row) return;
    const nameInput = row.querySelector('.batch-seller-name');
    const waInput = row.querySelector('.batch-seller-whatsapp');
    const supplierId = selectEl.value;
    if (!supplierId || supplierId === '__custom__') {
        if (supplierId === '__custom__') {
            nameInput.value = '';
            waInput.value = '';
            nameInput.focus();
        }
        return;
    }
    const supplier = _cachedSuppliers.find(s => s.id === supplierId);
    if (!supplier) return;
    nameInput.value = supplier.supplier_name || '';
    waInput.value = supplier.whatsapp_number || '';
}

/** Refresh all batch seller dropdowns when commodity changes */
function refreshBatchSellerDropdowns() {
    const commodity = document.getElementById('batch_commodity')?.value || '';
    const filtered = commodity
        ? _cachedSuppliers.filter(s => s.commodity && s.commodity.toLowerCase().includes(commodity.toLowerCase()))
        : _cachedSuppliers;
    document.querySelectorAll('.batch-supplier-select').forEach(sel => {
        const currentVal = sel.value;
        sel.innerHTML = '<option value="">— Select supplier —</option>';
        filtered.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.supplier_name} — ${s.city || ''} ${s.whatsapp_number ? '(' + s.whatsapp_number + ')' : ''}`;
            sel.appendChild(opt);
        });
        const customOpt = document.createElement('option');
        customOpt.value = '__custom__';
        customOpt.textContent = '✏️ Custom';
        sel.appendChild(customOpt);
        // Restore previous selection if still available
        if (currentVal) sel.value = currentVal;
    });
}

/** Remove a seller row by id */
function removeSellerRow(rowId) {
    const container = document.getElementById('sellerRowsContainer');
    if (container.children.length <= 2) {
        alert('At least 2 sellers are required for a batch negotiation.');
        return;
    }
    const el = document.getElementById(rowId);
    if (el) el.remove();
    // Re-label remaining rows
    Array.from(container.children).forEach((row, i) => {
        const lbl = row.querySelector('label');
        if (lbl) lbl.textContent = `Supplier ${i + 1}`;
    });
}

/** Collect batch form data and submit */
async function handleCreateBatch(e) {
    e.preventDefault();
    try {
        const sellerNames    = Array.from(document.querySelectorAll('.batch-seller-name')).map(el => el.value.trim());
        const sellerWas      = Array.from(document.querySelectorAll('.batch-seller-whatsapp')).map(el => el.value.trim());

        if (sellerNames.some(n => !n)) {
            alert('Please fill in all seller names.');
            return;
        }
        if (sellerNames.length < 2) {
            alert('Add at least 2 sellers.');
            return;
        }

        const sellers = sellerNames.map((name, i) => ({
            seller_name: name,
            seller_whatsapp: sellerWas[i] || null,
        }));

        const buyerStart = parseFloat(document.getElementById('batch_buyer_start').value);
        const buyerMax   = parseFloat(document.getElementById('batch_buyer_max').value);
        if (buyerMax <= buyerStart) {
            alert('Buyer max price must be higher than starting price.');
            return;
        }

        const data = {
            commodity:              document.getElementById('batch_commodity').value,
            quantity:               parseFloat(document.getElementById('batch_quantity').value),
            unit:                   document.getElementById('batch_unit').value,
            currency:               document.getElementById('batch_currency').value,
            buyer_starting_price:   buyerStart,
            buyer_reservation_price: buyerMax,
            buyer_delivery_days:    parseInt(document.getElementById('batch_buyer_delivery').value),
            buyer_payment_terms:    document.getElementById('batch_buyer_payment').value,
            buyer_strategy:         document.getElementById('batch_buyer_strategy').value,
            buyer_max_rounds:       parseInt(document.getElementById('batch_max_rounds').value),
            sellers,
            mandi_rate: null,  // can be extended with mandi input on batch form
            convergence_mode: 'MIDPOINT',
            approval_mode: 'AUTO',
        };

        closeCreateModal();

        const submitBtn = e.target.querySelector('button[type="submit"]');
        if (submitBtn) { submitBtn.textContent = '\u23F3 Running Batch Negotiations...'; submitBtn.disabled = true; }

        const batch = await API.createBatch(data);

        if (submitBtn) { submitBtn.textContent = '\u26a1 Launch Batch Negotiation'; submitBtn.disabled = false; }

        // Clear seller rows so next time starts fresh
        document.getElementById('sellerRowsContainer').innerHTML = '';
        _sellerRowCount = 0;

        viewBatch(batch.id);
    } catch (err) {
        console.error('Batch creation error:', err);
        alert('Failed to create batch: ' + err.message);
    }
}

/** Load and render the batch list table */
async function loadBatches() {
    const tbody = document.getElementById('batchTable');
    try {
        const batches = await API.listBatches();
        if (!batches.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align:center;padding:40px">No batch negotiations yet. Click \u26a1 New Batch Negotiation to start.</td></tr>';
            return;
        }
        tbody.innerHTML = batches.map(b => {
            const statusClass = b.status === 'COMPLETED' ? 'agreed' :
                                b.status === 'WALKAWAY'  ? 'walkaway' : 'info';
            const bestPrice = b.best_price ? `${b.currency} ${b.best_price.toLocaleString()}` : '\u2014';
            return `
                <tr style="cursor:pointer" onclick="viewBatch('${b.id}')">
                    <td>${b.commodity}</td>
                    <td>${b.quantity.toLocaleString()} ${b.unit}</td>
                    <td>${b.seller_count}</td>
                    <td style="color:var(--success);font-weight:600">${bestPrice}</td>
                    <td><span class="badge badge-${statusClass}">${b.status}</span></td>
                    <td>${new Date(b.created_at).toLocaleDateString()}</td>
                    <td>
                        <button onclick="event.stopPropagation();viewBatch('${b.id}')" style="padding:6px 14px;background:var(--primary);color:#fff;border:none;border-radius:4px;font-size:12px;font-weight:600;cursor:pointer">View Results</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align:center;padding:40px">Failed to load batches.</td></tr>';
        console.error('loadBatches error:', err);
    }
}

/** View a batch's ranked results */
async function viewBatch(batchId) {
    navigate('batch-detail');
    try {
        const batch = await API.getBatch(batchId);

        document.getElementById('batch_detail_title').textContent =
            `Batch: ${batch.commodity} \u2014 ${batch.quantity.toLocaleString()} ${batch.unit}`;

        // Summary cards
        const agreedCount = batch.negotiations.filter(n => n.status === 'AGREED').length;
        const bestNeg = batch.negotiations.find(n => n.id === batch.best_negotiation_id);
        document.getElementById('batch_summary').innerHTML = `
            <div><div class="text-muted" style="font-size:12px">Commodity</div><div style="font-weight:700">${batch.commodity}</div></div>
            <div><div class="text-muted" style="font-size:12px">Quantity</div><div style="font-weight:700">${batch.quantity.toLocaleString()} ${batch.unit}</div></div>
            <div><div class="text-muted" style="font-size:12px">Sellers</div><div style="font-weight:700">${batch.negotiations.length}</div></div>
            <div><div class="text-muted" style="font-size:12px">Agreements</div><div style="font-weight:700;color:var(--success)">${agreedCount}</div></div>
            <div><div class="text-muted" style="font-size:12px">Best Price</div><div style="font-weight:700;color:var(--success)">${bestNeg && bestNeg.final_price ? batch.currency + ' ' + bestNeg.final_price.toLocaleString() : '\u2014'}</div></div>
            <div><div class="text-muted" style="font-size:12px">Status</div><div><span class="badge badge-${batch.status.toLowerCase()}">${batch.status}</span></div></div>
        `;

        // Calculate highest agreed price for savings column
        const agreedPrices = batch.negotiations
            .filter(n => n.status === 'AGREED' && n.final_price)
            .map(n => n.final_price);
        const highestPrice = agreedPrices.length ? Math.max(...agreedPrices) : null;

        const tbody = document.getElementById('batchResultsTable');
        tbody.innerHTML = batch.negotiations.map((neg, idx) => {
            const isBest   = neg.id === batch.best_negotiation_id;
            const rank     = idx + 1;
            const rankBadge = isBest
                ? '<span style="background:#FFD700;color:#000;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700">\ud83c\udfc6 BEST</span>'
                : `#${rank}`;
            const finalPrice = neg.final_price ? `${batch.currency} ${neg.final_price.toLocaleString()}` : '\u2014';
            const totalVal   = neg.final_price ? `${batch.currency} ${(neg.final_price * neg.quantity).toLocaleString()}` : '\u2014';
            const savings    = (neg.status === 'AGREED' && neg.final_price && highestPrice && highestPrice > neg.final_price)
                ? `<span style="color:var(--success);font-weight:600">\u2212 ${batch.currency} ${(highestPrice - neg.final_price).toLocaleString()}</span>`
                : (neg.status === 'AGREED' ? '\u2014 (best)' : '\u2014');
            const statusClass = neg.status === 'AGREED' ? 'agreed' : neg.status === 'WALKAWAY' ? 'walkaway' : neg.status === 'HUMAN_APPROVAL' ? 'human_approval' : 'info';

            const rowStyle = isBest ? 'background:rgba(0,200,83,0.07);' : '';

            const actions = neg.status === 'AGREED' ? `
                <button onclick="viewContractById('${neg.id}')" style="padding:5px 10px;background:var(--primary);color:#fff;border:none;border-radius:4px;font-size:11px;font-weight:600;cursor:pointer;margin-right:4px">Contract</button>
                <button onclick="batchWhatsApp('${neg.id}','${neg.seller_whatsapp || ''}','${neg.seller_name || ''}')"
                    style="padding:5px 10px;background:#25D366;color:#fff;border:none;border-radius:4px;font-size:11px;font-weight:600;cursor:pointer;margin-right:4px">WhatsApp</button>
                <button onclick="acceptBestDeal('${batchId}','${neg.id}')" title="Mark as accepted deal"
                    style="padding:5px 10px;background:var(--success);color:#fff;border:none;border-radius:4px;font-size:11px;font-weight:600;cursor:pointer">\u2713 Accept</button>
            ` : '<span class="text-muted" style="font-size:11px">No deal</span>';

            return `<tr style="${rowStyle}">
                <td>${rankBadge}</td>
                <td><strong>${neg.seller_name || 'Seller ' + rank}</strong></td>
                <td>${finalPrice}</td>
                <td>${totalVal}</td>
                <td>${neg.current_round}</td>
                <td><span class="badge badge-${statusClass}">${neg.status.replace(/_/g, ' ')}</span></td>
                <td>${savings}</td>
                <td>${actions}</td>
            </tr>`;
        }).join('');

    } catch (err) {
        console.error('viewBatch error:', err);
        document.getElementById('batchResultsTable').innerHTML =
            '<tr><td colspan="8" class="text-muted" style="text-align:center;padding:40px">Failed to load batch results.</td></tr>';
    }
}

/** Mark a specific negotiation as the accepted/winner deal in a batch */
async function acceptBestDeal(batchId, negId) {
    try {
        await API.acceptBatch(batchId, negId);
        alert('\u2705 Deal accepted! This seller has been marked as the winner.');
        viewBatch(batchId);  // refresh
    } catch (err) {
        alert('Failed to accept deal: ' + err.message);
    }
}

/** Contact a specific seller from the batch via WhatsApp */
async function batchWhatsApp(negId, phone, sellerName) {
    if (!phone) {
        alert(`\u26A0\uFE0F No WhatsApp number was saved for ${sellerName || 'this seller'}.`);
        return;
    }
    try {
        const result = await API.notifyWhatsApp(negId);
        if (result.status === 'sent') {
            alert(`\u2705 WhatsApp message sent to ${result.phone}!`);
        } else if (result.status === 'dev_link') {
            const confirmed = confirm(
                `Click OK to open WhatsApp Web to contact ${sellerName || 'seller'}:\n${result.phone}`
            );
            if (confirmed) {
                window.open(`${result.wa_url}?text=${encodeURIComponent(result.message)}`, '_blank');
            }
        }
    } catch (err) {
        alert('WhatsApp failed: ' + err.message);
    }
}
