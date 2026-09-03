/**
 * API Client — communicates with FastAPI backend.
 * Handles JWT auth, request/response, and error handling.
 */
const API_BASE = window.location.origin;

const API = {
    token: localStorage.getItem('token'),

    setToken(token) {
        this.token = token;
        if (token) localStorage.setItem('token', token);
        else localStorage.removeItem('token');
    },

    async request(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };
        if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

        const opts = { method, headers };
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(`${API_BASE}${path}`, opts);

        if (res.status === 401) {
            this.setToken(null);
            showLogin();
            throw new Error('Unauthorized');
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }

        return res.json();
    },

    get: (path) => API.request('GET', path),
    post: (path, body) => API.request('POST', path, body),
    put: (path, body) => API.request('PUT', path, body),
    delete: (path) => API.request('DELETE', path),

    // ── Auth ──
    async register(data) {
        const user = await this.post('/api/v1/auth/register', data);
        return user;
    },

    async login(email, password) {
        const result = await this.post('/api/v1/auth/login', { email, password });
        this.setToken(result.access_token);
        return result;
    },

    logout() {
        this.setToken(null);
        showLogin();
    },

    async getMe() {
        return this.get('/api/v1/auth/me');
    },

    // ── Negotiations ──
    async getStats() { return this.get('/api/v1/negotiations/stats'); },
    async listNegotiations() { return this.get('/api/v1/negotiations'); },
    async getNegotiation(id) { return this.get(`/api/v1/negotiations/${id}`); },
    async getNegotiationStatus(id) { return this.get(`/api/v1/negotiations/${id}/status`); },
    async createNegotiation(data) { return this.post('/api/v1/negotiations', data); },
    async startNegotiation(id) { return this.post(`/api/v1/negotiations/${id}/start`); },
    async runRound(id) { return this.post(`/api/v1/negotiations/${id}/run-round`); },
    async runFull(id) { return this.post(`/api/v1/negotiations/${id}/run-full`); },
    async getOffers(id) { return this.get(`/api/v1/negotiations/${id}/offers`); },
    async getMessages(id) { return this.get(`/api/v1/negotiations/${id}/messages`); },

    // ── Human Approval ──
    async approveNegotiation(id) { return this.post(`/api/v1/negotiations/${id}/approve`); },
    async rejectNegotiation(id) { return this.post(`/api/v1/negotiations/${id}/reject`); },
    async sellerApproveNegotiation(id) { return this.post(`/api/v1/negotiations/${id}/seller-approve`); },
    async sellerRejectNegotiation(id) { return this.post(`/api/v1/negotiations/${id}/seller-reject`); },

    // ── Market Rates ──
    async getMarketRates(commodity) {
        const q = commodity ? `?commodity=${encodeURIComponent(commodity)}` : '';
        return this.get(`/api/v1/negotiations/market-rates${q}`);
    },
    async getMarketRate(commodity) {
        return this.get(`/api/v1/negotiations/market-rates/${encodeURIComponent(commodity)}`);
    },

    // ── Contracts & Audit ──
    async getContract(negId) { return this.get(`/api/v1/negotiations/${negId}/contract`); },
    async getAudit(negId) { return this.get(`/api/v1/negotiations/${negId}/audit`); },

    // WhatsApp notification
    async notifyWhatsApp(negId) {
        return this.post(`/api/v1/integrations/whatsapp/notify-agreement?negotiation_id=${negId}`);
    },

    // Fetch contract HTML with auth header
    async getContractHTML(negId) {
        const res = await fetch(`${API_BASE}/api/v1/negotiations/${negId}/contract/preview`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Accept': 'text/html',
            }
        });
        if (!res.ok) throw new Error('Failed to load contract preview');
        return res.text();
    },

    // ── Suppliers ──
    async listSuppliers(commodity) {
        const q = commodity ? `?commodity=${encodeURIComponent(commodity)}` : '';
        return this.get(`/api/v1/suppliers${q}`);
    },
    async seedSuppliers() { return this.post('/api/v1/suppliers/seed'); },

    // ── Batch Negotiations ──
    async createBatch(data) { return this.post('/api/v1/batches', data); },
    async listBatches() { return this.get('/api/v1/batches'); },
    async getBatch(id) { return this.get(`/api/v1/batches/${id}`); },
    async acceptBatch(batchId, negId) {
        return this.post(`/api/v1/batches/${batchId}/accept/${negId}`);
    },
};
