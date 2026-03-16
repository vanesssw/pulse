// ═══════════════════════════════════════
// PULSΞ API Client
// Backend connection with JWT auth
// ═══════════════════════════════════════

const API = {
  _backendOk: null,

  // ── Auth helpers (used by utils.js) ──
  isLoggedIn() {
    return !!localStorage.getItem('pulse_token');
  },

  getUser() {
    const email = localStorage.getItem('pulse_email');
    const token = localStorage.getItem('pulse_token');
    if (!email && !token) return null;
    return { email: email || '', method: token ? 'jwt' : 'email' };
  },

  async logout() {
    localStorage.removeItem('pulse_token');
    localStorage.removeItem('pulse_email');
    return true;
  },

  // ── Internal ──
  _headers() {
    const headers = { 'Content-Type': 'application/json' };
    
    // Add JWT token if available
    const token = localStorage.getItem('pulse_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    return headers;
  },

  async _req(method, path, body) {
    const o = { method, headers: this._headers() };
    if (body) o.body = JSON.stringify(body);
    const r = await fetch(API_BASE + path, o);
    
    // Handle unauthorized - logout user
    if (r.status === 401) {
      localStorage.removeItem('pulse_token');
      localStorage.removeItem('pulse_email');
      if (window.location.pathname !== '/') {
        window.location.href = '/';
      }
      throw { status: 401, message: 'Session expired' };
    }
    
    const d = await r.json();
    if (!r.ok) throw { status: r.status, ...d };
    return d;
  },

  async _backendAvailable() {
    if (this._backendOk !== null) return this._backendOk;
    try {
      const r = await fetch(API_BASE + '/health', { signal: AbortSignal.timeout(2000) });
      this._backendOk = r.ok;
    } catch { this._backendOk = false; }
    // Re-check every 30s
    setTimeout(() => { this._backendOk = null; }, 30000);
    return this._backendOk;
  },

  // ── Market (backend → direct CoinGecko fallback) ──
  async market() {
    try {
      if (await this._backendAvailable()) return await this._req('GET', '/api/market');
    } catch {}
    try {
      const r = await fetch(`https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana,dogecoin,ripple,cardano,the-open-network,avalanche-2&order=market_cap_desc&sparkline=false&price_change_percentage=1h,24h,7d`);
      if (r.ok) return await r.json();
    } catch {}
    return null;
  },

  async coin(id) {
    try {
      if (await this._backendAvailable()) return await this._req('GET', '/api/market/' + id);
    } catch {}
    try {
      const r = await fetch(`https://api.coingecko.com/api/v3/coins/${id}?localization=false&tickers=false&community_data=false&developer_data=false&sparkline=false`);
      if (r.ok) return await r.json();
    } catch {}
    return null;
  },

  async fng() {
    try {
      if (await this._backendAvailable()) return await this._req('GET', '/api/market/fng');
    } catch {}
    try {
      const r = await fetch('https://api.alternative.me/fng/?limit=1');
      return (await r.json())?.data?.[0] || null;
    } catch { return null; }
  },

  async topCoins(limit = 100) {
    try {
      if (await this._backendAvailable()) return await this._req('GET', `/api/market/top/${limit}`);
    } catch {}
    try {
      const r = await fetch(`https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=${limit}&page=1&sparkline=false&price_change_percentage=1h,24h,7d&x_cg_demo_api_key=CG-kS32QkmokagvYupg9KdJhuzq`);
      if (r.ok) return await r.json();
    } catch {}
    return null;
  },

  async cashtags(symbols = 'btc,eth,sol,doge,xrp,ada,ton,avax') {
    try {
      if (await this._backendAvailable()) {
        const result = await this._req('GET', `/api/market/cashtags?symbols=${symbols}`);
        // If backend returns error status, return empty data
        if (result && result.status === 'error') {
          console.warn('Twitter API error:', result.message);
          return { status: "error", data: [], message: result.message };
        }
        return result;
      }
    } catch (e) {
      console.error('Cashtags API error:', e);
    }
    return { status: "error", data: [], message: "Backend unavailable" };
  },

  async derivatives(symbol) {
    const s = String(symbol || '').trim();
    if (!s) return null;
    try {
      if (await this._backendAvailable()) {
        return await this._req('GET', `/api/market/derivatives/${encodeURIComponent(s)}`);
      }
    } catch {}
    return null;
  },

  async technicals(symbol, interval = '1h') {
    const s = String(symbol || '').trim();
    if (!s) return null;
    try {
      if (await this._backendAvailable()) {
        const iv = String(interval || '1h');
        return await this._req('GET', `/api/market/technicals/${encodeURIComponent(s)}?interval=${encodeURIComponent(iv)}`);
      }
    } catch {}
    return null;
  },

  // ── Radar ──
  async radarSignals(limit = 80) {
    try {
      if (await this._backendAvailable()) {
        return await this._req('GET', `/api/radar/signals?limit=${limit}`);
      }
    } catch {}
    return null;
  },

  async radarBreakdown(symbol) {
    try {
      if (await this._backendAvailable()) {
        return await this._req('GET', `/api/radar/breakdown/${encodeURIComponent(symbol)}`);
      }
    } catch {}
    return null;
  },

  // ── AI Agent ──
  async chat(message, context) {
    try {
      if (await this._backendAvailable()) {
        const d = await this._req('POST', '/api/agent/chat', { message, context });
        if (d.error) {
          console.error('AI Error:', d.error);
          return null;
        }
        return d.reply;
      }
    } catch (e) {
      console.error('Chat error:', e);
    }
    return null; // Caller uses fallback
  },

  async mission(task) {
    try {
      if (await this._backendAvailable()) {
        const d = await this._req('POST', '/api/agent/mission', { task });
        return d.synthesis;
      }
    } catch {}
    return null;
  },

  async signals(marketData = []) {
    try {
      if (await this._backendAvailable()) {
        const d = await this._req('POST', '/api/agent/signals', { market_data: JSON.stringify(marketData) });
        return d.signals;
      }
    } catch {}
    return null;
  },

  async getCachedSignals(hours = 24, limit = 50) {
    try {
      if (await this._backendAvailable()) {
        const d = await this._req('GET', `/api/agent/signals/cached?hours=${hours}&limit=${limit}`);
        return d.signals || [];
      }
    } catch {}
    return [];
  },

  async getLatestSignals(limit = 20) {
    try {
      if (await this._backendAvailable()) {
        const d = await this._req('GET', `/api/agent/signals/latest?limit=${limit}`);
        return d.signals || [];
      }
    } catch {}
    return [];
  },

  async getSignalsStats() {
    try {
      if (await this._backendAvailable()) {
        return await this._req('GET', '/api/agent/signals/stats');
      }
    } catch {}
    return null;
  },

  async cleanupOldSignals(hours = 168) {
    try {
      if (await this._backendAvailable()) {
        return await this._req('DELETE', `/api/agent/signals/cleanup?hours=${hours}`);
      }
    } catch {}
    return null;
  }
};
