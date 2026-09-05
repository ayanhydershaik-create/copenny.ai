// ═══════════════════════════════════════════════════════════════
//  Co Penny – Dashboard Logic v2 (Real-Time, No Dummy Values)
// ═══════════════════════════════════════════════════════════════

// ── Auth via Server Cookie ─────────────────────────────────────
// The actual auth gate is on /ui route (backend redirects if not authenticated).
// We fetch /api/me to get real user info from the server-side session.
async function initSession() {
    try {
        const res = await fetch('/api/me', { credentials: 'include' });
        if (!res.ok) {
            window.location.href = '/landing?error=unauthorized';
            return null;
        }
        const me = await res.json();
        // Check for mandatory plan selection
        if (me.authenticated && me.plan_confirmed === false) {
            showPlanGate();
        }
        // Update localStorage as cache for display purposes only
        localStorage.setItem('copenny_user_id', me.user_id || 'guest');
        localStorage.setItem('copenny_user_name', me.name || me.email?.split('@')[0] || 'Investor');
        return me;
    } catch (e) {
        // Cookie still valid but /api/me failed — keep going with stored values
        console.warn('[Auth] /api/me unavailable, using cached session');
        return null;
    }
}

async function handleLogout() {
    try {
        // Sign out from Firebase if available
        if (window.firebaseAuth?.auth) {
            await window.firebaseAuth.auth.signOut().catch(() => {});
        }
        // Clear backend cookie
        await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
    } catch (e) { /* silent */ }
    localStorage.clear();
    window.location.href = '/landing';
}

// ── Theme ──────────────────────────────────────────────────────

// ── tab switching ──────────────────────────────────────────────
function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.add('hidden');
        el.classList.remove('flex');
    });
    const activeTab = document.getElementById('tab-' + tab);
    if (activeTab) {
        activeTab.classList.remove('hidden');
        if (tab === 'chat') activeTab.classList.add('flex');
    }
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active-nav'));
    document.getElementById('nav-' + tab)?.classList.add('active-nav');
    const titles = { overview: 'Dashboard', chat: 'AI Advisor', data: 'Data Management', plans: 'Pricing Plans', analytics: 'Budgets & Analytics', goals: 'Savings Goals', subscriptions: 'Subscriptions' };
    const titleEl = document.getElementById('tabTitle');
    if (titleEl) titleEl.textContent = titles[tab] || tab;

    if (tab === 'goals') {
        renderSavingsGoals(window._widgetData?.monthlyAvg || 0, null);
    }
    if (tab === 'subscriptions') {
        loadSubscriptionsList();
    }

    // Lazy-load analytics on first switch
    if (tab === 'analytics' && !window._analyticsLoaded) {
        loadAnalyticsTab();
        window._analyticsLoaded = true;
    }
    if (window.innerWidth <= 768) closeSidebar();
}

function toggleUserMenu() {
    const dropdown = document.getElementById('userMenuDropdown');
    if (dropdown) {
        dropdown.classList.toggle('hidden');
    }
}

// Close user dropdown on outside click
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('userMenuDropdown');
    if (dropdown && !dropdown.classList.contains('hidden')) {
        const userMenuBtn = e.target.closest('[onclick*="toggleUserMenu"]');
        if (!userMenuBtn && !dropdown.contains(e.target)) {
            dropdown.classList.add('hidden');
        }
    }
});

function closeSidebar() {
    document.getElementById('dashboardSidebar')?.classList.remove('mobile-open');
    document.getElementById('sidebarOverlay')?.classList.add('hidden');
}

function toggleSidebar() {
    const sidebar = document.getElementById('dashboardSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar?.classList.toggle('mobile-open');
    overlay?.classList.toggle('hidden');
}

// ── User State ─────────────────────────────────────────────────
// These are set by initSession() on load; fallback to localStorage for speed
let currentUserId = localStorage.getItem('copenny_user_id') || 'guest';
let currentUserName = localStorage.getItem('copenny_user_name') || 'Investor';
let isDemoMode = currentUserId === 'demo_user';

function updateUserDisplay() {
    // Hide raw User ID — only show display name
    const el = document.getElementById('userIdDisplay');
    if (el) el.textContent = '';
    const ne = document.getElementById('userNameDisplay');
    if (ne) ne.textContent = currentUserName;
    const mne = document.getElementById('menuUserName');
    if (mne) mne.textContent = currentUserName;
    const ie = document.getElementById('userInitials');
    if (ie) ie.textContent = (currentUserName || 'U').charAt(0).toUpperCase();

    // UI Cleanup: Hide demo button if already in demo mode
    const demoBtn = document.querySelector('button[onclick="activateDemo()"]');
    if (demoBtn) {
        if (isDemoMode) demoBtn.classList.add('hidden');
        else demoBtn.classList.remove('hidden');
    }

    updateSubscriptionStatus();
}

async function updateSubscriptionStatus() {
    if (isDemoMode) {
        const badge = document.getElementById('tierBadge');
        if (badge) {
            badge.textContent = 'Demo';
            badge.className = 'text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold uppercase tracking-wider cursor-pointer';
        }
        return;
    }
    try {
        const res = await fetch(`/subscription/status?user_id=${currentUserId}`, { credentials: 'include' });
        const data = await res.json();
        const badge = document.getElementById('tierBadge');
        if (badge) {
            badge.textContent = data.tier || 'Free';
            const cls = data.tier === 'pro' ? 'bg-amber-500/20 text-amber-500'
                : data.tier === 'enterprise' ? 'bg-purple-500/20 text-purple-400'
                    : 'bg-slate-500/20 text-slate-400';
            badge.className = `text-[9px] px-1.5 py-0.5 rounded ${cls} font-bold uppercase tracking-wider cursor-pointer hover:opacity-80 transition-all`;
        }
    } catch (e) { /* silent */ }
}

// ── Plan Selection Gate ─────────────────────────────────────────
function showPlanGate() {
    const gate = document.getElementById('planGateOverlay');
    if (gate) {
        gate.classList.remove('hidden');
        document.body.style.overflow = 'hidden'; 
    }
}

function hidePlanGate() {
    const gate = document.getElementById('planGateOverlay');
    if (gate) {
        gate.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

async function fetchSafety(url, options = {}, retries = 3, delay = 1000) {
    try {
        const headers = { 'Cache-Control': 'no-cache', ...(options.headers || {}) };
        const res = await fetch(url, { credentials: 'include', ...options, headers });
        
        if (res.status === 429 && retries > 0) {
            console.warn(`Rate limited (429) for ${url}. Retrying in ${delay}ms... (${retries} retries left)`);
            await new Promise(resolve => setTimeout(resolve, delay));
            return fetchSafety(url, options, retries - 1, delay * 2);
        }
        
        if (!res.ok) return { has_data: false, status: 'error', error: res.status };
        return await res.json();
    } catch (e) {
        console.warn(`Fetch failed for ${url}:`, e);
        return { has_data: false, status: 'error' };
    }
}

async function selectPlan(tier) {
    if (!currentUserId || currentUserId === 'guest') {
        showToast('Please login first', 'error');
        return;
    }
    
    showToast(`⏳ Activating your ${tier} plan...`, 'info');
    try {
        const res = await fetch('/subscription/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUserId, tier: tier, months: 12 })
        });
        const data = await res.json();
        if (data.success) {
            hidePlanGate();
            await initSession();
            updateUserDisplay();
            await refreshDashboard();
            showToast(`🚀 ${tier.toUpperCase()} plan activated! Welcome to Co Penny.`, 'success');
        } else {
            showToast('Failed to select plan. Please try again.', 'error');
        }
    } catch (e) {
        showToast('Connection error. Please try again.', 'error');
    }
}

// ══════════════════════════════════════════════════════════════
//  DEMO MODE
// ══════════════════════════════════════════════════════════════
async function activateDemo() {
    showToast('🎬 Loading demo data…', 'info');
    try {
        const res = await fetch('/demo/activate', { credentials: 'include' });
        const data = await res.json();
        if (data.success) {
            localStorage.setItem('copenny_authenticated', 'true');
            localStorage.setItem('copenny_user_id', data.user_id);
            localStorage.setItem('copenny_user_name', data.user_name);
            currentUserId = data.user_id;
            currentUserName = data.user_name;
            isDemoMode = true;
            updateUserDisplay();
            await refreshDashboard();
            await loadAlertHistory();
            showToast('✅ Demo mode activated! Explore Co Penny freely.', 'success');
        }
    } catch (e) {
        showToast('Failed to activate demo mode.', 'error');
    }
}

// ══════════════════════════════════════════════════════════════
//  DASHBOARD REFRESH
// ══════════════════════════════════════════════════════════════
async function refreshDashboard() {
    try {

        // Add timestamp to GET requests to bust query cache
        const ts = `&_t=${Date.now()}`;
        const [summary, health, subs, pred, insight] = await Promise.all([
            fetchSafety(`/dashboard/summary?user_id=${currentUserId}${ts}`),
            fetchSafety(`/analytics/health-score?user_id=${currentUserId}${ts}`),
            fetchSafety(`/analytics/subscriptions?user_id=${currentUserId}${ts}`),
            fetchSafety(`/analytics/predictions?user_id=${currentUserId}&budget=50000${ts}`),
            fetchSafety(`/api/ai/financial-insight`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' },
                body: JSON.stringify({ user_id: currentUserId })
            })
        ]);

        renderSummaryCards(summary, health, subs, pred, insight);
        if (summary && summary.has_data) {
            renderSpendingChart(pred);
            renderCategoryChart(insight);
        }
    } catch (e) {
        console.error('Core dashboard refresh error:', e);
    }
}

function renderSummaryCards(summary, health, subs, pred, insight) {
    // Priority: insight.financialHealthScore > health.total > 0
    const activeHealth = (insight && insight.has_data !== false && insight.financialHealthScore)
        || (health && health.total)
        || 0;

    // Priority: insight.topSpendingCategory (only if real data returned)
    const insightHasData = insight && insight.has_data !== false && insight.status !== 'no_data';
    const activeTopCat = (insightHasData && insight.topSpendingCategory && insight.topSpendingCategory !== 'N/A')
        ? insight.topSpendingCategory
        : 'Upload CSV to analyse';

    // Savings: use insight value or 0
    const activeSavings = (insightHasData && insight.potentialSavings) ? insight.potentialSavings : 0;

    // AI insight text
    const activeInsight = (insightHasData && insight.insight)
        ? insight.insight
        : 'No data found. Upload a CSV to get AI guidance.';

    // Health Score
    setText('healthScoreLabel', activeHealth);
    updateHealthRing(activeHealth);
    setText('stat-health-note', activeHealth > 70 ? 'Excellent Balance ✓' : 'Optimization Required');

    // Top Category
    setText('stat-top-category', activeTopCat);
    
    // Potential Savings
    setText('stat-savings', `₹ ${activeSavings.toLocaleString('en-IN')}`);
    
    // AI Insight
    const insightEl = document.getElementById('stat-ai-insight');
    if (insightEl) {
        insightEl.innerHTML = formatMessage(activeInsight);
        insightEl.classList.remove('italic', 'opacity-50');
    }

    // Secondary UI Sync (Keeping legacy fields for compatibility if they exist in HTML)
    setText('stat-balance', summary.has_data ? `₹ ${summary.balance.toLocaleString('en-IN')}` : '₹ --');
    setText('stat-subs', `₹ ${(subs.monthly_total || 0).toLocaleString('en-IN')}`);
}

function updateHealthRing(score) {
    const ring = document.getElementById('healthRing');
    const scoreLabel = document.getElementById('healthScoreLabel');
    if (!ring) return;
    const circumference = 2 * Math.PI * 36;
    const offset = circumference - (score / 100) * circumference;
    ring.style.strokeDasharray = `${circumference}`;
    ring.style.strokeDashoffset = `${offset}`;
    const color = score >= 80 ? '#10b981' : score >= 55 ? '#fbbf24' : '#ef4444';
    ring.style.stroke = color;
    if (scoreLabel) scoreLabel.textContent = score;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value !== undefined && value !== null ? value : '--';
}

// ── Charts ─────────────────────────────────────────────────────
async function renderSpendingChart(pred) {
    const el = document.getElementById('trendChart');
    if (!el || !pred.monthly_history || pred.monthly_history.length === 0) return;

    const isDark = true;
    const labels = pred.monthly_history.map(m => m.month);
    const actuals = pred.monthly_history.map(m => m.spent);
    const forecast = [...actuals.map(() => null)]; // null for past
    forecast.push(pred.predicted_total);
    labels.push('Next Month (Predicted)');
    actuals.push(null);

    const opts = {
        chart: { type: 'area', height: 180, sparkline: { enabled: false }, toolbar: { show: false }, fontFamily: 'Inter, sans-serif', background: 'transparent' },
        theme: { mode: isDark ? 'dark' : 'light' },
        colors: ['#F59E0B', '#FBBF24'],
        fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.04, stops: [0, 100] } },
        dataLabels: { enabled: false },
        stroke: { curve: 'smooth', width: 2 },
        series: [
            { name: 'Actual', data: actuals },
            { name: 'Predicted', data: forecast },
        ],
        xaxis: { categories: labels, labels: { style: { fontSize: '10px', colors: '#777777' } }, axisBorder: { show: false }, axisTicks: { show: false } },
        yaxis: { labels: { formatter: v => v ? `₹${(v / 1000).toFixed(0)}K` : '', style: { fontSize: '10px', colors: '#777777' } } },
        tooltip: { y: { formatter: v => v ? `₹${Math.round(v).toLocaleString('en-IN')}` : 'Predicted' } },
        grid: { borderColor: '#202020', strokeDashArray: 4 },
        legend: { position: 'top', fontSize: '10px', labels: { colors: '#888888' } },
    };

    if (window._trendChart) { window._trendChart.destroy(); }
    window._trendChart = new ApexCharts(el, opts);
    await window._trendChart.render();
}

async function renderCategoryChart(analyticsData) {
    const el = document.getElementById('categoryChart');
    if (!el) return;

    try {
        let names = [];
        let vals = [];
        
        if (analyticsData && analyticsData.monthlySummary) {
            // Use real analytics from the new engine
            const summary = analyticsData.monthlySummary;
            names = Object.keys(summary);
            vals = Object.values(summary);
        } else {
            // Fallback to prediction endpoint data
            const predRes = await fetch(`/analytics/predictions?user_id=${currentUserId}&budget=50000`, { credentials: 'include' });
            const pred = await predRes.json();
            const cats = (pred.category_predictions || []).slice(0, 7);
            names = cats.map(c => c.category);
            vals = cats.map(c => c.predicted);
        }

        if (names.length === 0) return;

        const isDark = true;
        const opts = {
            chart: { type: 'donut', height: 180, toolbar: { show: false }, fontFamily: 'Inter, sans-serif', background: 'transparent' },
            theme: { mode: isDark ? 'dark' : 'light' },
            series: vals,
            labels: names,
            colors: ['#F59E0B', '#FBBF24', '#D97706', '#B45309', '#78350F', '#451A03', '#262626'],
            plotOptions: { pie: { donut: { size: '68%', labels: { show: true, total: { show: true, label: 'Total Spend', color: '#FFFFFF', formatter: () => `₹${vals.reduce((a, b) => a + b, 0).toFixed(0)}` } } } } },
            legend: { position: 'bottom', fontSize: '10px', labels: { colors: '#888888' } },
            tooltip: { y: { formatter: v => `₹${Math.round(v).toLocaleString('en-IN')}` } },
            dataLabels: { enabled: false },
            stroke: { show: false }
        };

        if (window._categoryChart) { window._categoryChart.destroy(); }
        window._categoryChart = new ApexCharts(el, opts);
        await window._categoryChart.render();
    } catch (e) { console.error('Category chart error:', e); }
}

// ══════════════════════════════════════════════════════════════
//  ANALYTICS TAB
// ══════════════════════════════════════════════════════════════
async function loadAnalyticsTab() {
    await Promise.allSettled([
        loadHealthBreakdown(),
        loadSubscriptionsList(),
        loadPredictionSummary(),
        loadSmartAlerts(),
    ]);
}

async function loadHealthBreakdown() {
    const el = document.getElementById('healthBreakdownContainer');
    if (!el) return;
    try {
        const ts = `&_t=${Date.now()}`;
        const data = await fetchSafety(`/analytics/health-score?user_id=${currentUserId}${ts}`);
        if (!data) return;

        if (!data.breakdown || Object.keys(data.breakdown).length === 0) {
            el.innerHTML = `<p class="text-slate-500 text-sm text-center py-4">Upload transaction data to see your health score breakdown.</p>`;
            return;
        }

        const dimLabels = {
            savings_habit: 'Savings Habit',
            budget_discipline: 'Budget Discipline',
            spending_stability: 'Spending Stability',
            subscription_mgmt: 'Subscription Mgmt',
        };

        el.innerHTML = Object.entries(data.breakdown).map(([key, dim]) => {
            const pct = Math.round((dim.score / dim.max) * 100);
            const color = pct >= 85 ? '#10b981' : pct >= 65 ? '#f59e0b' : '#ef4444';
            return `
                <div class="mb-4">
                    <div class="flex justify-between text-xs mb-1">
                        <span class="text-slate-300 font-medium">${dimLabels[key] || key}</span>
                        <span style="color:${color}" class="font-bold">${dim.score}/${dim.max} — ${dim.label}</span>
                    </div>
                    <div class="w-full bg-slate-800 rounded-full h-2">
                        <div class="h-2 rounded-full transition-all duration-700" style="width:${pct}%;background:${color}"></div>
                    </div>
                </div>`;
        }).join('');

        // Gamification badge
        const tier = data.level || {};
        const badgeEl = document.getElementById('gamificationBadge');
        if (badgeEl && tier.name) {
            badgeEl.innerHTML = `
                <span class="text-3xl">${tier.badge}</span>
                <div>
                    <p class="text-sm font-bold text-white">Level ${tier.level}: ${tier.name}</p>
                    <p class="text-xs text-slate-400">Financial Health: ${data.total}/100</p>
                </div>`;
            badgeEl.style.borderColor = tier.color;
        }
    } catch (e) { console.error('Health breakdown error:', e); }
}

async function loadSubscriptionsList() {
    const el = document.getElementById('subscriptionsContainer');
    if (!el) return;
    try {
        const ts = `&_t=${Date.now()}`;
        const data = await fetchSafety(`/analytics/subscriptions?user_id=${currentUserId}${ts}`);
        if (!data) return;

        if (!data.items || data.items.length === 0) {
            el.innerHTML = `<p class="text-slate-500 text-sm text-center py-4">No recurring payments detected yet.</p>`;
            return;
        }

        el.innerHTML = data.items.map(s => `
            <div class="flex items-center justify-between p-3 rounded-xl hover:bg-white/5 transition-all">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center text-xs">📱</div>
                    <div>
                        <p class="text-xs font-semibold text-white">${s.merchant}</p>
                        <p class="text-[10px] text-slate-500">${s.months_seen} months detected ${s.flag}</p>
                    </div>
                </div>
                <span class="text-xs font-bold text-slate-200">₹${s.amount.toLocaleString('en-IN')}/mo</span>
            </div>`).join('');

        const totalEl = document.getElementById('subMonthlyTotal');
        if (totalEl) totalEl.textContent = `₹${(data.monthly_total || 0).toLocaleString('en-IN')}/month`;
    } catch (e) { console.error('Subscriptions error:', e); }
}

async function loadPredictionSummary() {
    const el = document.getElementById('predictionContainer');
    if (!el) return;
    try {
        const ts = `&_t=${Date.now()}`;
        const data = await fetchSafety(`/analytics/predictions?user_id=${currentUserId}&budget=50000${ts}`);
        if (!data) return;

        if (data.status !== 'success') {
            el.innerHTML = `<p class="text-slate-500 text-sm text-center py-4">Upload transaction data to see spending predictions.</p>`;
            return;
        }

        const alertColor = data.over_budget ? 'text-red-400' : 'text-emerald-400';
        const alertBg = data.over_budget ? 'bg-red-500/10 border-red-500/30' : 'bg-emerald-500/10 border-emerald-500/30';

        let html = `
            <div class="p-4 rounded-xl border ${alertBg} mb-4">
                <p class="${alertColor} text-sm font-medium">${data.alert}</p>
                ${data.coffee_tip ? `<p class="text-amber-400 text-xs mt-2">${data.coffee_tip}</p>` : ''}
            </div>
            <p class="text-xs text-slate-500 uppercase font-bold tracking-wider mb-3">Category Forecast (Next Month)</p>
            <div class="space-y-2">`;

        const cats = (data.category_predictions || []).slice(0, 6);
        cats.forEach(c => {
            html += `
                <div class="flex justify-between items-center">
                    <span class="text-xs text-slate-300">${c.category}</span>
                    <span class="text-xs font-bold text-slate-200">₹${Math.round(c.predicted).toLocaleString('en-IN')}</span>
                </div>`;
        });
        html += `</div>`;
        el.innerHTML = html;
    } catch (e) { console.error('Prediction error:', e); }
}

async function loadSmartAlerts() {
    // Fetch from the smart-alerts endpoint and render in the overview tab
    try {
        const ts = `&_t=${Date.now()}`;
        const data = await fetchSafety(`/analytics/smart-alerts?user_id=${currentUserId}${ts}`);
        // Re-render alert history to pick up new smart alerts
        // Re-render alert history to pick up new smart alerts
        await loadAlertHistory();
    } catch (e) { /* silent */ }
}

// ══════════════════════════════════════════════════════════════
//  AI CHAT
// ══════════════════════════════════════════════════════════════
const QUICK_QUESTIONS = [
    'Where did I spend the most this month?',
    'How can I save ₹5,000?',
    'Show my spending trends',
    'What subscriptions am I paying for?',
    'Predict my expenses for next month',
];

function renderQuickQuestions() {
    const container = document.getElementById('quickQuestions');
    if (!container) return;
    container.innerHTML = QUICK_QUESTIONS.map(q => `
        <button onclick="askQuickQuestion('${q}')"
                class="text-[11px] px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-emerald-500/20 hover:text-emerald-400 text-slate-400 border border-slate-700/50 hover:border-emerald-500/30 transition-all whitespace-nowrap">
            ${q}
        </button>`).join('');
}

function askQuickQuestion(q) {
    const input = document.getElementById('chatInput');
    if (input) {
        input.value = q;
        handleChat(null);
    }
}

function appendMessage(who, text, visualizations = null) {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    // Clear indicator
    removeTypingIndicator();

    const div = document.createElement('div');
    div.className = (who === 'user' ? 'msg-user self-end' : 'msg-bot') + ' p-4 rounded-2xl max-w-2xl text-sm leading-relaxed flex flex-col gap-3 shadow-xl';

    const label = document.createElement('div');
    label.className = `chat-label ${who === 'user' ? 'label-user' : 'label-bot'}`;
    label.textContent = who === 'user' ? 'YOU' : 'CO PENNY';
    div.appendChild(label);

    const textDiv = document.createElement('div');
    textDiv.className = 'text-white/90 transition-all';
    textDiv.innerHTML = formatMessage(text);
    div.appendChild(textDiv);

    if (visualizations) {
        for (const [type, data] of Object.entries(visualizations)) {
            if (data && data.startsWith('data:image')) {
                const vizWrapper = document.createElement('div');
                vizWrapper.className = 'bg-slate-900/50 p-4 rounded-xl border border-white/5 mt-2';
                vizWrapper.innerHTML = `<p class="text-[9px] uppercase font-black text-slate-500 mb-2 tracking-widest">${type.replace(/_/g, ' ')}</p>`;
                const img = document.createElement('img');
                img.src = data;
                img.className = 'w-full rounded-lg shadow-2xl';
                vizWrapper.appendChild(img);
                div.appendChild(vizWrapper);
            }
        }
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function formatMessage(text) {
    if (!text) return '';
    // Bold **text**
    let formatted = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Bullet points starting with • or -
    formatted = formatted.replace(/^[•\-] (.+)/gm, '<li class="ml-4 list-disc">$1</li>');
    // Newlines to <br>
    formatted = formatted.replace(/\n/g, '<br>');
    return formatted;
}

function showTypingIndicator() {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const div = document.createElement('div');
    div.id = 'typingIndicator';
    div.className = 'msg-bot p-4 rounded-2xl max-w-xs text-sm';
    div.innerHTML = `
        <div class="chat-label label-bot">Co Penny</div>
        <div class="flex gap-1 items-center">
            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style="animation-delay:0ms"></span>
            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style="animation-delay:150ms"></span>
            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style="animation-delay:300ms"></span>
            <span class="text-emerald-400 text-[10px] font-black uppercase tracking-widest ml-2">Analyzing...</span>
        </div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
    document.getElementById('typingIndicator')?.remove();
}

async function handleChat(ev) {
    if (ev) ev.preventDefault();
    const input = document.getElementById('chatInput');
    const msg = input ? input.value.trim() : '';
    if (!msg) return;
    if (input) input.value = '';

    appendMessage('user', msg);
    showTypingIndicator();

    const btn = document.getElementById('sendBtn');
    if (btn) { btn.disabled = true; btn.textContent = '…'; }

    let streamedSuccessfully = false;

    // ── Primary: Real-time SSE Streaming via 6 Specialized Featherless Agents ──
    try {
        const streamRes = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg, context: [] }),
            credentials: 'include'
        });

        if (streamRes.ok && streamRes.body) {
            const reader = streamRes.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let botMessageDiv = null;
            let botTextDiv = null;
            let accumulatedText = '';
            let activeAgent = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete chunk

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed.startsWith('data:')) continue;
                    const jsonStr = trimmed.slice(5).trim();
                    if (!jsonStr) continue;

                    try {
                        const evData = JSON.parse(jsonStr);

                        if (evData.type === 'progress') {
                            const indText = document.querySelector('#typingIndicator span.text-emerald-400');
                            if (indText) indText.textContent = evData.message;
                        } else if (evData.type === 'agent') {
                            activeAgent = evData.name;
                        } else if (evData.type === 'token') {
                            if (!botMessageDiv) {
                                removeTypingIndicator();
                                const container = document.getElementById('chat-messages');
                                botMessageDiv = document.createElement('div');
                                botMessageDiv.className = 'msg-bot p-4 rounded-2xl max-w-2xl text-sm leading-relaxed flex flex-col gap-3 shadow-xl';

                                const label = document.createElement('div');
                                const agentLabel = activeAgent ? `CO PENNY • ${activeAgent.toUpperCase()} AGENT` : 'CO PENNY';
                                label.className = 'chat-label label-bot';
                                label.textContent = agentLabel;
                                botMessageDiv.appendChild(label);

                                botTextDiv = document.createElement('div');
                                botTextDiv.className = 'text-white/90 transition-all';
                                botMessageDiv.appendChild(botTextDiv);

                                if (container) {
                                    container.appendChild(botMessageDiv);
                                    container.scrollTop = container.scrollHeight;
                                }
                            }

                            accumulatedText += evData.content;
                            if (botTextDiv) {
                                botTextDiv.innerHTML = formatMessage(accumulatedText);
                                const container = document.getElementById('chat-messages');
                                if (container) container.scrollTop = container.scrollHeight;
                            }
                            streamedSuccessfully = true;
                        } else if (evData.type === 'done') {
                            streamedSuccessfully = true;
                        }
                    } catch (parseErr) {
                        // ignore parse errors for partial chunks
                    }
                }
            }
        }
    } catch (streamErr) {
        console.warn('[Chat] SSE streaming encountered error, falling back:', streamErr);
    }

    // ── Fallback: Standard /chat Endpoint if streaming was unavailable ──
    if (!streamedSuccessfully) {
        let data = null;
        for (let attempt = 0; attempt < 3; attempt++) {
            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: 'local', message: msg, context: [], user_id: currentUserId }),
                    credentials: 'include'
                });
                data = await res.json();
                if (data.status !== 'error' || attempt === 2) break;
                await new Promise(r => setTimeout(r, 400 * (attempt + 1)));
            } catch (e) {
                if (attempt === 2) {
                    data = { answer: "I'm having trouble connecting right now. Please try again in a moment. 🔄", status: 'error' };
                } else {
                    await new Promise(r => setTimeout(r, 800));
                }
            }
        }

        removeTypingIndicator();

        if (data) {
            if (data.status === 'limit_reached') {
                appendMessage('bot', `${data.answer} 🚀 Upgrade to Pro for more queries.`);
            } else {
                let answer = data.answer;
                if (!answer && data.status === 'error') {
                    answer = "I apologize, but I'm having a hard time reaching my brain right now. 🧠 Please try again in a few seconds.";
                }
                appendMessage('bot', answer || "I'm not sure how to respond to that properly. Could you rephrase?", data.visualizations);
            }
        }
    } else {
        removeTypingIndicator();
    }

    if (btn) { btn.disabled = false; btn.textContent = 'TRANSMIT'; }
    updateSubscriptionStatus();
}

// ══════════════════════════════════════════════════════════════
//  DATA MANAGEMENT
// ══════════════════════════════════════════════════════════════
async function checkStatus() {
    try {
        const res = await fetch(`/personalization/status/${currentUserId}`, { credentials: 'include' });
        const data = await res.json();
        const statusDiv = document.getElementById('personalizationStatus');
        if (!statusDiv) return;
        if (data.has_data) {
            statusDiv.innerHTML = `<div class="bg-emerald-500/10 text-emerald-400 p-4 rounded-2xl border border-emerald-500/20 text-xs">
                <strong>✓ Data Synchronized</strong><br>${data.metadata?.total_transactions || '?'} records found</div>`;
            if (data.has_model) setText('modelStatusMsg', 'High Accuracy Active');
        }
    } catch (e) { /* silent */ }
}

async function uploadCSV() {
    const fileInput = document.getElementById('csvFile');
    const file = fileInput ? fileInput.files[0] : null;
    if (!file) return showToast('Please select a CSV or Excel file.', 'error');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', currentUserId);
    formData.append('overwrite', document.getElementById('overwriteCheck').checked);

    const btn = document.getElementById('uploadBtn');
    setBtn(btn, true, '⏳ Processing…');

    try {
        const res = await fetch('/personalization/upload', { method: 'POST', body: formData, credentials: 'include' });
        const data = await res.json();

        if (data.success === false && data.error?.includes('limit')) {
            document.getElementById('uploadStatus').innerHTML =
                `<p class="text-[10px] mt-2 text-amber-500 uppercase font-bold">${data.error}</p>
                 <button onclick="switchTab('plans')" class="text-[9px] text-indigo-400 hover:underline mt-1 font-bold">UPGRADE PLAN →</button>`;
        } else {
            const col = data.success ? 'text-emerald-400' : 'text-red-400';
            document.getElementById('uploadStatus').innerHTML = `<p class="text-[10px] mt-2 ${col} uppercase font-bold">${data.message || data.error}</p>`;
        }

        if (data.success) {
            window._analyticsLoaded = false; // Force re-fetch on tab switch
            await initWidgets(); // Immediately pull fresh widget data
            await refreshDashboard();
            await loadAlertHistory();
            // Also refresh analytics data immediately so it's ready
            await loadAnalyticsTab();
            window._analyticsLoaded = true; // Mark as freshly loaded
            showToast('✅ Data uploaded! Dashboard updated.', 'success');
            // Switch to analytics tab to show results
            switchTab('analytics');
        }
        checkStatus();
        updateSubscriptionStatus();
    } catch (e) {
        document.getElementById('uploadStatus').innerHTML = `<p class="text-[10px] mt-2 text-red-400 uppercase font-bold">Upload Error</p>`;
        showToast('Upload failed. Please try again.', 'error');
    } finally {
        setBtn(btn, false, 'Upload and Scan');
    }
}

async function trainModel() {
    const btn = document.getElementById('trainBtn');
    setBtn(btn, true, '⚙️ Calibrating…');
    try {
        const formData = new FormData();
        formData.append('user_id', currentUserId);
        formData.append('retrain', true);
        const res = await fetch('/personalization/train', { method: 'POST', body: formData, credentials: 'include' });
        const data = await res.json();
        const status = document.getElementById('trainStatus');
        if (data.success) {
            status.innerHTML = `<p class="text-[10px] mt-2 text-emerald-400 uppercase font-bold">Success: ${Math.round(data.test_accuracy * 100)}% Accuracy ✓</p>`;
            setText('modelStatusMsg', 'Personalized Intelligence Ready');
            await refreshDashboard();
            showToast('🧠 Model calibrated successfully!', 'success');
        } else {
            status.innerHTML = `<p class="text-[10px] mt-2 text-red-400 uppercase font-bold">${data.error}</p>`;
        }
    } catch (e) {
        document.getElementById('trainStatus').innerHTML = `<p class="text-[10px] mt-2 text-red-400 uppercase font-bold">Calibration Failed</p>`;
    } finally {
        setBtn(btn, false, 'Calibrate AI Model');
    }
}

async function deleteUserData() {
    if (!confirm('Delete all your data? This cannot be undone.')) return;
    const btn = document.getElementById('deleteDataBtn');
    setBtn(btn, true, 'Deleting…');
    try {
        const res = await fetch(`/personalization/data?user_id=${currentUserId}`, { method: 'DELETE', credentials: 'include' });
        const data = await res.json();
        if (data.success) {
            window._analyticsLoaded = false; // Force re-fetch
            setText('uploadStatus', '');
            document.getElementById('personalizationStatus').innerHTML = '';
            setText('modelStatusMsg', 'Ready for Calibration');
            await refreshDashboard();
            await loadAlertHistory();
            showToast('🗑️ All data deleted.', 'info');
        }
    } catch (e) { /* silent */ }
    finally { setBtn(btn, false, 'Delete All Data'); }
}

// ── Alert History ───────────────────────────────────────────────
async function loadAlertHistory() {
    const container = document.getElementById('alertHistoryContainer');
    if (!container) return;
    try {
        const res = await fetch(`/alerts/history?user_id=${currentUserId}`, { credentials: 'include' });
        const data = await res.json();
        if (data.success && data.alerts?.length > 0) {
            container.innerHTML = data.alerts.map(a => {
                const borderColor = a.severity === 'high' ? 'border-red-500' : a.severity === 'medium' ? 'border-amber-500' : 'border-blue-500';
                const bgColor = a.severity === 'high' ? 'bg-red-500/20' : a.severity === 'medium' ? 'bg-amber-500/20' : 'bg-blue-500/20';
                const icon = a.type === 'large_transaction' ? '💰' : a.type === 'unusual_spending' ? '📈' : a.type === 'budget_alert' ? '⚠️' : '🔔';
                return `
                    <div class="flex gap-4 items-start p-4 rounded-xl hover:bg-white/5 transition-all border-l-4 ${borderColor}">
                        <div class="w-10 h-10 rounded-full ${bgColor} flex items-center justify-center shrink-0">${icon}</div>
                        <div class="flex-1">
                            <p class="text-sm font-semibold text-white mb-1">${a.title || 'Alert'}</p>
                            <p class="text-xs text-slate-400">${a.message}</p>
                            <p class="text-[10px] text-slate-600 mt-1">${a.created_at ? new Date(a.created_at).toLocaleString('en-IN') : ''}</p>
                        </div>
                    </div>`;
            }).join('');
        } else {
            container.innerHTML = `<div class="text-center py-8 text-slate-500">
                <p class="text-sm">No alerts yet</p>
                <p class="text-xs mt-1">Upload transaction data to receive financial insights</p></div>`;
        }
    } catch (e) { /* silent */ }
}

async function clearAlertHistory() {
    if (!confirm('🗑️ Are you sure you want to clear your entire alert history? This cannot be undone.')) return;
    
    showToast('⏳ Clearing alert history...', 'info');
    try {
        const res = await fetch(`/alerts/history?user_id=${currentUserId}`, { 
            method: 'DELETE', 
            credentials: 'include' 
        });
        const data = await res.json();
        
        if (data.success) {
            showToast('✅ Alert history cleared successfully.', 'success');
            await loadAlertHistory();
        } else {
            showToast(`❌ Error: ${data.error || 'Failed to clear history'}`, 'error');
        }
    } catch (e) {
        showToast('❌ Connection error while clearing history.', 'error');
        console.error('Clear alerts error:', e);
    }
}

// ── Helpers ────────────────────────────────────────────────────
function setBtn(btn, disabled, text) {
    if (!btn) return;
    btn.disabled = disabled;
    btn.textContent = text;
}

function showToast(message, type = 'info') {
    const existing = document.getElementById('copenny-toast');
    if (existing) existing.remove();
    const colors = { success: 'bg-emerald-600', error: 'bg-red-600', info: 'bg-slate-700' };
    const toast = document.createElement('div');
    toast.id = 'copenny-toast';
    toast.className = `fixed bottom-6 right-6 z-50 ${colors[type] || colors.info} text-white text-sm px-5 py-3 rounded-2xl shadow-xl flex items-center gap-3 transition-all duration-300`;
    toast.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()" class="text-white/70 hover:text-white text-lg leading-none">×</button>`;
    document.body.appendChild(toast);
    setTimeout(() => toast?.remove(), 4500);
}

// ══════════════════════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Initialize session FIRST
    const user = await initSession();
    if (user) {
        currentUserId = user.user_id;
        currentUserName = user.name || user.email.split('@')[0];
        isDemoMode = currentUserId === 'demo_user';
    }

    updateUserDisplay();
    refreshDashboard();
    loadAlertHistory();
    renderQuickQuestions();

    // Event listeners
    document.getElementById('chatForm')?.addEventListener('submit', handleChat);
    document.getElementById('uploadBtn')?.addEventListener('click', uploadCSV);
    document.getElementById('trainBtn')?.addEventListener('click', trainModel);
    document.getElementById('deleteDataBtn')?.addEventListener('click', deleteUserData);
    document.getElementById('clearHistoryBtn')?.addEventListener('click', clearAlertHistory);
    document.getElementById('csvFile')?.addEventListener('change', e => {
        setText('fileNameDisplay', e.target.files[0] ? e.target.files[0].name : 'Choose CSV or Excel File');
    });

    // Chat keyboard shortcut (Enter to send, Shift+Enter for newline)
    document.getElementById('chatInput')?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleChat(null);
        }
    });

    checkStatus();

    // Load new widgets
    initWidgets();
});


// ══════════════════════════════════════════════════════════════
//  WIDGETS: Daily Spending Limit, Health Score, Savings Goals, Scenario Sim
// ══════════════════════════════════════════════════════════════

// -- State shared across widgets --
window._widgetData = {
    monthlyAvg: 0,
    healthScore: 72,
    weeklySpend: 0,
    dailyLimit: 2000,
    goals: []
};

async function initWidgets() {
    try {
        const ts = `&_t=${Date.now()}`;
        
        // Fetch independently to prevent Promise.all from crashing everything if one fails
        let stats = { monthly_avg: 0, week_spent: 0, today_spent: 0, has_data: false };
        try {
            stats = await fetchSafety(`/analytics/current-stats?user_id=${currentUserId}${ts}`);
        } catch (e) {
            console.error('[Widgets] current-stats error:', e);
        }

        let health = {};
        try {
            health = await fetchSafety(`/analytics/health-score?user_id=${currentUserId}${ts}`);
        } catch (e) {
            console.error('[Widgets] health-score error:', e);
        }

        const monthlyAvg = stats?.monthly_avg || 0;
        const weeklySpend = stats?.week_spent || 0;
        const todaySpend = stats?.today_spent || 0;

        // Daily limit calculation
        const rawLimit = Math.round(monthlyAvg / 30);
        const dailyLimit = rawLimit > 0 ? Math.ceil(rawLimit / 500) * 500 : 2000;

        window._widgetData = {
            monthlyAvg,
            weeklySpend,
            dailyLimit,
            todaySpend,
            healthScore: health?.total || 72,
            hasData: stats?.has_data || false
        };

        // Render non-AI components immediately
        renderDailySpendingWidget(todaySpend, dailyLimit, weeklySpend, monthlyAvg);
        renderHealthScoreWidget(health);
        renderSavingsGoals(monthlyAvg, null);

        // ══════════════════════════════════════════════════════════════
        //  STAGGERED LOADING: Delay AI calls slightly to prevent burst 429s
        // ══════════════════════════════════════════════════════════════
        setTimeout(async () => {
            console.log('[Widgets] Starting delayed AI analysis (2.5s delay)...');
            let insight = {};
            try {
                insight = await fetchSafety(`/api/ai/financial-insight`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' },
                    body: JSON.stringify({ user_id: currentUserId })
                });
            } catch (e) {
                console.error('[Widgets] insight error:', e);
            }

            // Update state with AI data if returned
            if (insight && insight.financialHealthScore) {
                if (window._widgetData) window._widgetData.healthScore = insight.financialHealthScore;
                renderHealthScoreWidget(health); // Re-render with AI health score if better
            }
            renderSavingsGoals(monthlyAvg, insight);
        }, 2500); 

    } catch (e) {
        console.warn('[Widgets] Critical Init error:', e);
        // Render with defaults so UI is never broken
        renderDailySpendingWidget(0, 2000, 0, 0);
    }
}

// ── Daily Spending Limit ──────────────────────────────────────
function renderDailySpendingWidget(todaySpend, dailyLimit, weeklySpend, monthlyAvg) {
    const pct = dailyLimit > 0 ? Math.min(100, Math.round((todaySpend / dailyLimit) * 100)) : 0;
    const remaining = Math.max(0, dailyLimit - todaySpend);
    const over = todaySpend > dailyLimit;

    // Progress bar
    const bar = document.getElementById('dsl-bar');
    if (bar) {
        bar.style.width = `${pct}%`;
        bar.style.background = over
            ? 'linear-gradient(90deg,#ef4444,#dc2626)'
            : pct > 75
                ? 'linear-gradient(90deg,#fbbf24,#f59e0b)'
                : 'linear-gradient(90deg,#10b981,#059669)';
    }

    // Labels
    const limitEl = document.getElementById('dsl-limit-text');
    if (limitEl) limitEl.textContent = `₹${dailyLimit.toLocaleString('en-IN')}`;

    const progressEl = document.getElementById('dsl-progress-text');
    if (progressEl) {
        const spendColor = over ? '#ef4444' : pct > 75 ? '#fbbf24' : '#10b981';
        progressEl.innerHTML = `<span style="color:${spendColor}">₹${todaySpend.toLocaleString('en-IN')}</span> / <span class="text-slate-200">₹${dailyLimit.toLocaleString('en-IN')}</span>`;
    }

    // Status badge
    const badge = document.getElementById('dsl-status-badge');
    if (badge) {
        if (over) {
            badge.textContent = '🚨 OVER LIMIT';
            badge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest bg-red-500/10 text-red-400 border border-red-500/20';
        } else if (pct > 75) {
            badge.textContent = '⚡ CAUTION';
            badge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest bg-yellow-500/10 text-yellow-400 border border-yellow-500/20';
        } else {
            badge.textContent = '✅ ON TRACK';
            badge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
        }
    }

    setText('dsl-remaining', `₹${remaining.toLocaleString('en-IN')}`);
    setText('dsl-weekly', weeklySpend > 0 ? `₹${(weeklySpend / 1000).toFixed(1)}K` : '₹0');
    setText('dsl-monthly-avg', monthlyAvg > 0 ? `₹${(monthlyAvg / 1000).toFixed(1)}K` : '₹0');
}

// ── Financial Health Score Gauge ──────────────────────────────
function renderHealthScoreWidget(health) {
    const score = health?.total || window._widgetData.healthScore || 72;
    const arcEl = document.getElementById('health-gauge-arc');
    const scoreEl = document.getElementById('fhs-score');

    if (arcEl) {
        const total = 235; // total arc length
        const offset = total - (score / 100) * total;
        arcEl.style.strokeDashoffset = offset;
        const color = score >= 80 ? '#10b981' : score >= 60 ? '#05b0d6' : '#fbbf24';
        arcEl.style.stroke = color;
        if (scoreEl) {
            scoreEl.textContent = score;
            scoreEl.style.color = color;
        }
    }

    // Sub-metrics derived from health breakdown
    if (health?.breakdown) {
        const savings = health.breakdown.savings_habit;
        const budget = health.breakdown.budget_discipline;
        const subs = health.breakdown.subscription_mgmt;

        if (savings) {
            const rate = Math.round((savings.score / savings.max) * 24); // proxy: 24% max
            const rateEl = document.getElementById('fhs-savings-rate');
            if (rateEl) {
                rateEl.textContent = `${rate}%`;
                rateEl.style.color = rate >= 20 ? '#10b981' : '#fbbf24';
            }
        }
        if (subs) {
            const debtRatio = Math.max(0, 30 - Math.round((subs.score / subs.max) * 30));
            const debtEl = document.getElementById('fhs-debt-ratio');
            if (debtEl) {
                debtEl.textContent = `${debtRatio}%`;
                debtEl.style.color = debtRatio < 30 ? '#10b981' : '#ef4444';
            }
        }
        if (budget) {
            const emergencyPct = Math.round((budget.score / budget.max) * 100);
            const emEl = document.getElementById('fhs-emergency');
            if (emEl) {
                emEl.textContent = `${emergencyPct}%`;
                emEl.style.color = emergencyPct >= 100 ? '#10b981' : '#fbbf24';
            }
        }
    }
}

// ── Savings Goals ─────────────────────────────────────────────
const DEFAULT_GOALS = [
    { emoji: '🛡️', name: 'Emergency Fund', current: 0, target: 150000 },
    { emoji: '✈️', name: 'Vacation 2026', current: 0, target: 80000 },
    { emoji: '💻', name: 'New Laptop', current: 0, target: 65000 },
];

async function fetchGoalsFromBackend() {
    try {
        const res = await fetch('/api/goals', { credentials: 'include' });
        if (res.ok) {
            const data = await res.json();
            if (data.goals && data.goals.length > 0) {
                return data.goals.map(g => {
                    const match = g.name && g.name.match(/^(\p{Emoji})/u);
                    const emoji = match ? match[0] : '🎯';
                    return {
                        id: g.id || g.goal_id,
                        emoji: emoji,
                        name: g.name,
                        current: parseFloat(g.current_amount || g.saved_amount || 0),
                        target: parseFloat(g.target_amount || 0)
                    };
                });
            }
        }
    } catch (e) {
        console.warn('[Goals] Backend fetch failed, falling back to local:', e);
    }
    return null;
}

function getGoals() {
    try {
        const stored = localStorage.getItem(`copenny_goals_${currentUserId}`);
        return stored ? JSON.parse(stored) : null;
    } catch { return null; }
}

function saveGoals(goals) {
    localStorage.setItem(`copenny_goals_${currentUserId}`, JSON.stringify(goals));
}

async function renderSavingsGoals(monthlyAvg, insight) {
    let goals = await fetchGoalsFromBackend();
    if (!goals || goals.length === 0) {
        goals = getGoals();
    }
    if (!goals || goals.length === 0) {
        // Seed with smart defaults based on data
        goals = DEFAULT_GOALS.map(g => ({
            id: null,
            emoji: g.emoji || '🎯',
            name: g.name,
            current: Math.min(g.target, Math.round((monthlyAvg || 48200) * 0.15 * (Math.random() * 4 + 2))),
            target: g.target
        }));
        saveGoals(goals);
    }
    window._widgetData.goals = goals;

    // 1. Overview Tab Widget Container
    const overviewContainer = document.getElementById('savings-goals-container');
    if (overviewContainer) {
        if (goals.length === 0) {
            overviewContainer.innerHTML = `<p class="text-[#666666] text-xs text-center py-4">No goals yet. Add your first savings goal!</p>`;
        } else {
            overviewContainer.innerHTML = goals.map((g, idx) => {
                const pct = Math.min(100, Math.round(((g.current || 0) / (g.target || 1)) * 100));
                const color = pct >= 90 ? '#10B981' : pct >= 50 ? '#05b0d6' : '#F59E0B';
                const days = 730;
                const dailyTargetTotal = Math.max(0, (g.target * 1.08) - g.current) / days;
                const dailyTarget = Math.round(dailyTargetTotal);
                const emoji = g.emoji || (g.name && g.name.match(/^(\p{Emoji})/u)?.[0]) || '🎯';
                const displayName = g.name.replace(/^(\p{Emoji}|\s)+/u, '').trim() || g.name;

                return `
                <div class="group/goal cursor-pointer" onclick="switchTab('goals')">
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs font-bold text-white truncate max-w-[180px]">${emoji} ${displayName}</span>
                    <span class="text-xs font-mono font-bold" style="color:${color}">
                      ₹${Number(g.current || 0).toLocaleString('en-IN')} / ₹${Number(g.target || 0).toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div class="flex justify-between items-center mb-1.5">
                    <span class="text-[9px] text-[#777777] uppercase font-bold tracking-wider">Target: ₹${dailyTarget}/day</span>
                    <span class="text-[10px] font-mono font-bold" style="color:${color}">${pct}%</span>
                  </div>
                  <div class="w-full bg-[#1e1e1e] rounded-full h-2 overflow-hidden border border-[#262626]">
                    <div class="h-2 rounded-full transition-all duration-700" style="width:${pct}%;background:${color}"></div>
                  </div>
                </div>`;
            }).join('');
        }
    }

    // 2. Full Goals Tab Container (#tab-goals -> #goals-page-container)
    const pageContainer = document.getElementById('goals-page-container');
    if (pageContainer) {
        if (goals.length === 0) {
            pageContainer.innerHTML = `
                <div class="text-center py-12 text-[#666666]">
                    <div class="text-4xl mb-3">🎯</div>
                    <p class="text-sm font-semibold text-white">No Savings Goals Configured</p>
                    <p class="text-xs text-[#777777] mt-1 mb-5">Set milestone targets for emergencies, travel, real estate, or gadget acquisitions.</p>
                    <button onclick="openAddGoalModal()" class="bg-[#F59E0B] hover:bg-[#F59E0B]/90 text-black px-5 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider transition-all">
                        + Create First Goal
                    </button>
                </div>`;
        } else {
            pageContainer.innerHTML = goals.map((g, idx) => {
                const pct = Math.min(100, Math.round(((g.current || 0) / (g.target || 1)) * 100));
                const color = pct >= 100 ? '#10B981' : pct >= 50 ? '#05b0d6' : '#F59E0B';
                const days = 730;
                const dailyTargetTotal = Math.max(0, (g.target * 1.08) - g.current) / days;
                const dailyTarget = Math.round(dailyTargetTotal);
                const remaining = Math.max(0, (g.target || 0) - (g.current || 0));
                const emoji = g.emoji || (g.name && g.name.match(/^(\p{Emoji})/u)?.[0]) || '🎯';
                const displayName = g.name.replace(/^(\p{Emoji}|\s)+/u, '').trim() || g.name;

                return `
                <div class="p-5 rounded-2xl bg-[#141414] border border-[#242424] hover:border-[#333333] transition-all flex flex-col lg:flex-row lg:items-center justify-between gap-5">
                    <div class="flex items-start sm:items-center gap-4 flex-1">
                        <div class="w-12 h-12 rounded-xl flex items-center justify-center text-2xl shrink-0" style="background: ${color}15; border: 1px solid ${color}30">
                            ${emoji}
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex flex-wrap items-center gap-2 mb-1">
                                <h3 class="text-sm font-bold text-white tracking-wide truncate">${displayName}</h3>
                                ${pct >= 100 
                                    ? '<span class="text-[9px] font-black uppercase px-2 py-0.5 rounded bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30">Target Met 🎉</span>'
                                    : `<span class="text-[9px] font-bold text-[#888888] bg-[#1F1F1F] px-2 py-0.5 rounded border border-[#2E2E2E]">₹${remaining.toLocaleString('en-IN')} remaining</span>`
                                }
                            </div>
                            <div class="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-[#888888]">
                                <span>Saved: <strong style="color: ${color}" class="font-mono">₹${Number(g.current || 0).toLocaleString('en-IN')}</strong></span>
                                <span>Target: <strong class="text-white font-mono">₹${Number(g.target || 0).toLocaleString('en-IN')}</strong></span>
                                <span>Daily Pace: <strong class="text-[#CCCCCC] font-mono">₹${dailyTarget}/day</strong></span>
                            </div>
                            <div class="w-full bg-[#1c1c1c] rounded-full h-2.5 mt-3 overflow-hidden border border-[#282828]">
                                <div class="h-2.5 rounded-full transition-all duration-700" style="width: ${pct}%; background: ${color}"></div>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 shrink-0 self-end lg:self-center">
                        <span class="text-sm font-mono font-black mr-2" style="color: ${color}">${pct}%</span>
                        <button onclick="addFundsToGoal(${idx}, 1000)" class="px-3 py-1.5 rounded-xl bg-[#1C1C1C] hover:bg-[#282828] text-xs font-semibold text-white border border-[#2E2E2E] transition-colors" title="Add ₹1,000 to this goal">
                            +₹1,000
                        </button>
                        <button onclick="addFundsToGoal(${idx}, 5000)" class="px-3 py-1.5 rounded-xl bg-[#1C1C1C] hover:bg-[#282828] text-xs font-semibold text-white border border-[#2E2E2E] transition-colors" title="Add ₹5,000 to this goal">
                            +₹5,000
                        </button>
                        <button onclick="deleteGoal(${idx})" class="p-2 rounded-xl bg-[#1C1C1C] hover:bg-[#EF4444]/20 hover:text-[#EF4444] text-[#777777] border border-[#2E2E2E] transition-colors" title="Delete Goal">
                            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                    </div>
                </div>`;
            }).join('');
        }
    }
}

function openAddGoalModal() {
    const modal = document.getElementById('addGoalModal');
    if (modal) {
        modal.classList.remove('hidden');
        document.getElementById('goalInputName')?.focus();
    }
}

function closeAddGoalModal() {
    const modal = document.getElementById('addGoalModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    const form = document.getElementById('addGoalForm');
    if (form) form.reset();
}

async function submitAddGoal(e) {
    if (e) e.preventDefault();
    const nameInput = document.getElementById('goalInputName');
    const targetInput = document.getElementById('goalInputTarget');
    const currentInput = document.getElementById('goalInputCurrent');
    const emojiInput = document.getElementById('goalInputEmoji');

    const rawName = nameInput ? nameInput.value.trim() : '';
    const target = targetInput ? parseFloat(targetInput.value) : 0;
    const current = currentInput ? (parseFloat(currentInput.value) || 0) : 0;
    const emoji = (emojiInput && emojiInput.value.trim()) || '🎯';

    if (!rawName || target <= 0) {
        showToast('Please enter a goal name and valid target amount.', 'error');
        return;
    }

    const fullName = `${emoji} ${rawName}`;

    let createdId = null;
    try {
        const res = await fetch('/api/goals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: fullName,
                target_amount: target,
                current_amount: current
            }),
            credentials: 'include'
        });
        if (res.ok) {
            const created = await res.json();
            createdId = created?.id || created?.goal_id;
        }
    } catch (err) {
        console.warn('[Goals] Backend creation fallback:', err);
    }

    const goals = window._widgetData?.goals || getGoals() || [];
    goals.push({
        id: createdId || `local_${Date.now()}`,
        emoji: emoji,
        name: fullName,
        current: current,
        target: target
    });
    saveGoals(goals);

    closeAddGoalModal();
    await renderSavingsGoals(window._widgetData?.monthlyAvg || 0, null);
    showToast(`🎯 Goal "${rawName}" created successfully!`, 'success');
}

async function addFundsToGoal(idx, amount) {
    const goals = window._widgetData?.goals || getGoals() || [];
    if (!goals[idx]) return;
    const g = goals[idx];

    // If backend goal ID exists, update backend
    if (g.id && !String(g.id).startsWith('local_')) {
        try {
            await fetch(`/api/goals/${g.id}/add-savings?amount=${amount}`, {
                method: 'POST',
                credentials: 'include'
            });
        } catch (e) {
            console.warn('[Goals] Backend update error:', e);
        }
    }

    g.current = (g.current || 0) + amount;
    saveGoals(goals);
    await renderSavingsGoals(window._widgetData?.monthlyAvg || 0, null);
    const cleanName = g.name.replace(/^(\p{Emoji}|\s)+/u, '').trim() || g.name;
    if (g.current >= g.target) {
        showToast(`🎉 Congratulations! You reached your goal for "${cleanName}"!`, 'success');
    } else {
        showToast(`💰 Added ₹${amount.toLocaleString('en-IN')} to "${cleanName}"!`, 'success');
    }
}

async function deleteGoal(idx) {
    const goals = window._widgetData?.goals || getGoals() || [];
    if (!goals[idx]) return;
    const g = goals[idx];
    const cleanName = g.name.replace(/^(\p{Emoji}|\s)+/u, '').trim() || g.name;
    if (!confirm(`Are you sure you want to delete the "${cleanName}" savings goal?`)) return;

    if (g.id && !String(g.id).startsWith('local_')) {
        try {
            await fetch(`/api/goals/${g.id}`, {
                method: 'DELETE',
                credentials: 'include'
            });
        } catch (e) {
            console.warn('[Goals] Backend delete error:', e);
        }
    }

    goals.splice(idx, 1);
    saveGoals(goals);
    await renderSavingsGoals(window._widgetData?.monthlyAvg || 0, null);
    showToast(`🗑️ Goal "${cleanName}" deleted.`, 'info');
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAddGoalModal();
});

// Close modal on backdrop click
document.getElementById('addGoalModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'addGoalModal') closeAddGoalModal();
});

// ── Scenario Simulation ───────────────────────────────────────
function updateSimLabel(val) {
    const el = document.getElementById('sim-pct-label');
    if (el) el.textContent = `${val}%`;
}

function runScenarioSimulation() {
    const slider = document.getElementById('sim-slider');
    const pct = slider ? parseInt(slider.value) : 10;
    const monthlyAvg = window._widgetData.monthlyAvg || 48200;
    const healthScore = window._widgetData.healthScore || 72;

    const saved = Math.round(monthlyAvg * (pct / 100));
    const newSpend = monthlyAvg - saved;
    const annualSave = saved * 12;
    const healthBoost = Math.min(100, Math.round(healthScore + pct * 0.12));

    // Populate results
    setText('sim-old-spend', `₹${(monthlyAvg / 1000).toFixed(1)}K`);
    setText('sim-new-spend', `₹${(newSpend / 1000).toFixed(1)}K`);
    setText('sim-annual-save', `₹${(annualSave / 1000).toFixed(0)}K`);
    setText('sim-old-health', `${healthScore}/100`);
    setText('sim-new-health', `${healthBoost}/100`);

    const monthSave = saved.toLocaleString('en-IN');
    const annualStr = annualSave.toLocaleString('en-IN');
    const summaryEl = document.getElementById('sim-summary-text');
    if (summaryEl) {
        summaryEl.innerHTML = `📌 Reducing spend by <strong class="text-yellow-400">${pct}%</strong> saves <strong class="text-emerald-400">₹${monthSave}/month</strong> and <strong class="text-emerald-400">₹${annualStr}</strong> annually!`;
    }

    const results = document.getElementById('sim-results');
    if (results) {
        results.classList.remove('hidden');
        results.style.animation = 'slideUp 0.5s ease forwards';
    }
}

function resetSimulation() {
    const slider = document.getElementById('sim-slider');
    if (slider) slider.value = 10;
    updateSimLabel(10);
    const results = document.getElementById('sim-results');
    if (results) results.classList.add('hidden');
}
