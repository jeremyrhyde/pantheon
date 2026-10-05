/* Pantheon status screen — a HUD for the desk display (1024×600 and up).
 * One snapshot, ../api/overview, polled every 3 s; the main Pi's health is
 * always visible, modules and devices open in slide-up sheets. */

const STATUS_POLL_MS = 3000;
const STALE_AFTER_MS = 10_000;
const SHEET_IDLE_MS = 60_000;
const SHEET_KEY = 'pantheon:status:sheet';
const DIAL_START = -135;  // degrees clockwise from 12 o'clock
const DIAL_SWEEP = 270;
const DIAL_R = 49;
const TEMP_MAX = 90;
const SWIPE_CLOSE_PX = 80;

function polar(deg, r) {
  const rad = (deg * Math.PI) / 180;
  return [60 + r * Math.sin(rad), 60 - r * Math.cos(rad)];
}

function band(key, value) {
  if (value == null) return 'off';
  if (key === 'temp') return value < 60 ? 'ok' : value < 75 ? 'warn' : value < 80 ? 'hot' : 'bad';
  return value < 75 ? 'ok' : value < 90 ? 'warn' : 'bad';
}

function statusApp() {
  return {
    data: null,
    started: Date.now(),
    lastOkAt: null,
    now: Date.now(),
    sheet: null,
    shownSheet: null,  // what the sheet shows; kept through the slide-out
    polling: false,
    idleAt: Date.now(),
    touchY: null,
    resumedAt: Date.now(),
    // One path for all eleven ticks: Alpine's x-for can't run inside <svg>.
    ticks: Array.from({ length: 11 }, (_, i) => {
      const deg = DIAL_START + (i * DIAL_SWEEP) / 10;
      const [x1, y1] = polar(deg, 56);
      const [x2, y2] = polar(deg, 52);
      return `M ${x1.toFixed(2)} ${y1.toFixed(2)} L ${x2.toFixed(2)} ${y2.toFixed(2)}`;
    }).join(' '),

    init() {
      startStarfield(this.$refs.sky, { dim: 0.45, speed: 0.4 });
      try { this.sheet = localStorage.getItem(SHEET_KEY); } catch { this.sheet = null; }
      if (this.sheet !== 'modules' && this.sheet !== 'devices') this.sheet = null;
      this.shownSheet = this.sheet;
      this.poll();
      setInterval(() => this.poll(), STATUS_POLL_MS);
      // Hidden tabs skip polls; on return, restart the stale clock and poll
      // at once so the skipped polls don't read as "UNREACHABLE".
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) return;
        this.now = this.resumedAt = Date.now();
        this.poll();
      });
      setInterval(() => {
        this.now = Date.now();
        if (this.sheet && this.now - this.idleAt > SHEET_IDLE_MS) this.closeSheet();
      }, 1000);
    },

    async poll() {
      if (document.hidden || this.polling) return;
      this.polling = true;
      try {
        const res = await fetch('../api/overview', { signal: AbortSignal.timeout(STATUS_POLL_MS) });
        if (!res.ok) throw new Error(String(res.status));
        this.data = await res.json();
        this.lastOkAt = Date.now();
      } catch {
        // keep the last snapshot; `stale` raises the alert bar
      } finally {
        this.polling = false;
      }
    },

    // ---- data -------------------------------------------------------------
    get host() { return this.data?.host ?? {}; },
    get history() { return this.data?.history ?? {}; },
    get modules() { return this.data?.modules ?? []; },
    get devices() { return this.data?.devices ?? []; },
    get stale() { return this.now - Math.max(this.lastOkAt ?? this.started, this.resumedAt) > STALE_AFTER_MS; },
    get overall() { return this.stale ? 'offline' : (this.data?.overall ?? 'offline'); },
    get clock() { return new Date(this.now).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); },

    get hostWarn() {
      const t = this.host.throttle;
      if (t?.now.under_voltage) return 'UNDER-VOLTAGE';
      if (t?.now.throttled) return 'THROTTLED';
      if (this.host.temp_c >= 80) return 'HOT';
      if (t && Object.values(t.now).some(Boolean)) return 'LIMITED';
      return null;
    },

    get overallText() {
      if (this.stale) return 'PANTHEON UNREACHABLE';
      const plural = (n, word) => `${n} ${word}${n > 1 ? 'S' : ''}`;
      const count = (list, state) => list.filter((x) => x.state === state).length;
      const enabled = this.modules.filter((m) => m.enabled);
      const listed = this.devices.filter((d) => d.listed);
      const parts = [];
      if (count(enabled, 'offline')) parts.push(`${plural(count(enabled, 'offline'), 'MODULE')} OFFLINE`);
      if (this.hostWarn) parts.push(`HOST ${this.hostWarn}`);
      if (count(enabled, 'degraded')) parts.push(`${plural(count(enabled, 'degraded'), 'MODULE')} DEGRADED`);
      if (count(listed, 'offline')) parts.push(`${plural(count(listed, 'offline'), 'DEVICE')} OFFLINE`);
      if (count(listed, 'kiosk_issue')) parts.push(`${plural(count(listed, 'kiosk_issue'), 'KIOSK ISSUE')}`);
      return parts.length ? parts.slice(0, 2).join(' · ') : 'ALL SYSTEMS NOMINAL';
    },

    get dials() {
      const h = this.host;
      const pct = (used, total) => (used != null && total ? (100 * used) / total : null);
      const dial = (key, label, value, max, unit, history, min, hmax, sub) => ({
        key, label, unit, history: history ?? [], min, max: hmax, sub,
        fraction: value == null ? 0 : Math.min(1, value / max),
        text: value == null ? '—' : Math.round(value),
        band: band(key, value),
      });
      return [
        dial('cpu', 'CPU', h.cpu_percent, 100, '%', this.history.cpu, 0, 100,
             h.load ? `load ${h.load[0].toFixed(2)}` : ''),
        dial('mem', 'MEMORY', pct(h.mem_used, h.mem_total), 100, '%', this.history.mem, 0, 100,
             `${this.bytes(h.mem_used)} / ${this.bytes(h.mem_total)}`),
        dial('temp', 'TEMP', h.temp_c, TEMP_MAX, '°C', this.history.temp, 0, TEMP_MAX,
             h.temp_c == null ? 'no sensor' : h.temp_c >= 80 ? 'throttling range' : ''),
        dial('disk', 'DISK', pct(h.disk_used, h.disk_total), 100, '%', this.history.disk, 0, 100,
             `${this.bytes(h.disk_used)} / ${this.bytes(h.disk_total)}`),
      ];
    },

    get loadBars() {
      const cores = (this.host.cpu_per_core ?? []).length || 1;
      return (this.host.load ?? []).map((v, i) => ({
        label: ['1m', '5m', '15m'][i], text: v.toFixed(2), pct: Math.min(100, (100 * v) / cores),
      }));
    },
    get cores() { return (this.host.cpu_per_core ?? []).map((v) => Math.min(100, Math.round(v))); },
    get wifiLevel() {
      const dbm = this.host.wifi_dbm;
      if (dbm == null) return 0;
      return dbm >= -55 ? 4 : dbm >= -65 ? 3 : dbm >= -75 ? 2 : dbm >= -85 ? 1 : 0;
    },
    get lamps() {
      const t = this.host.throttle;
      return [['under_voltage', 'UNDERVOLT'], ['throttled', 'THROTTLED'],
              ['freq_capped', 'FREQ CAP'], ['soft_temp_limit', 'TEMP LIMIT']]
        .map(([key, label]) => ({
          label,
          cls: !t ? 'lamp--na' : t.now[key] ? 'lamp--now' : t.since_boot[key] ? 'lamp--past' : '',
        }));
    },
    get units() {
      // gateway is null for the first second after startup: unknown, not down.
      const gw = this.host.units?.gateway;
      return [{ label: 'GATEWAY', cls: gw === true ? 'lamp--ok' : gw === false ? 'lamp--now' : 'lamp--na' },
              { label: 'APP', cls: this.stale ? 'lamp--now' : 'lamp--ok' }];
    },

    // ---- formatting -------------------------------------------------------
    arc(fraction) {
      if (!(fraction > 0)) return '';
      const sweep = DIAL_SWEEP * Math.min(fraction, 0.9999);
      const [x1, y1] = polar(DIAL_START, DIAL_R);
      const [x2, y2] = polar(DIAL_START + sweep, DIAL_R);
      return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${DIAL_R} ${DIAL_R} 0 ${sweep > 180 ? 1 : 0} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
    },
    spark(points, min, max) {
      if (!points || points.length < 2) return '';
      const values = points.map((p) => p[1]);
      const lo = min ?? Math.min(...values);
      const hi = max ?? Math.max(...values, lo + 1);
      const n = points.length - 1;
      return points.map((p, i) => {
        const v = Math.min(Math.max(p[1], lo), hi);
        return `${((i / n) * 100).toFixed(1)},${(23 - ((v - lo) / (hi - lo || 1)) * 22).toFixed(1)}`;
      }).join(' ');
    },
    duration(seconds) {
      if (seconds == null) return '—';
      const s = Math.floor(seconds);
      if (s < 60) return `${s}s`;
      const m = Math.floor(s / 60);
      if (m < 60) return `${m}m`;
      const h = Math.floor(m / 60);
      if (h < 48) return `${h}h ${m % 60}m`;
      return `${Math.floor(h / 24)}d ${h % 24}h`;
    },
    ago(t) {
      if (t == null) return 'never';
      const ms = typeof t === 'number' ? t : Date.parse(t);
      const s = Math.round((this.now - ms) / 1000);
      if (s < 0) return `in ${this.duration(-s)}`;
      if (s < 5) return 'now';
      return `${this.duration(s)} ago`;
    },
    timeOf(iso) { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); },
    bytes(n) {
      if (n == null) return '—';
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let i = 0;
      while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
      return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
    },
    rate(n) { return n == null ? '—' : `${this.bytes(n)}/s`; },
    formatStat(s) {
      if (s.value == null) return '—';
      if (s.kind === 'time') return this.ago(s.value);
      if (s.kind === 'percent') return `${s.value}%`;
      return String(s.value);
    },
    get deviceCountText() {
      const listed = this.devices.filter((d) => d.listed);
      const unlisted = this.devices.length - listed.length;
      if (!listed.length) return unlisted ? `${unlisted} unlisted` : '0/0';
      return this.countText(listed) + (unlisted ? ` · ${unlisted} unlisted` : '');
    },
    // The module the heartbeat's kiosk_url points at ('home' for the root).
    kioskTarget(d) {
      try {
        return new URL(d.heartbeat?.kiosk_url).pathname.split('/').filter(Boolean)[0] || 'home';
      } catch {
        return null;
      }
    },
    pingText(ms) {
      if (ms == null) return '—';
      return ms < 1 ? '<1 ms' : `${Math.round(ms * 10) / 10} ms`;
    },
    countText(list) { return `${list.filter((x) => x.state === 'online').length}/${list.length}`; },
    moduleNote(m) { return m.enabled ? (m.last_api_call ? this.ago(m.last_api_call) : '') : 'off'; },
    deviceBars(d) {
      const hb = d.heartbeat ?? {};
      const memPct = hb.mem_total_mb ? (100 * hb.mem_used_mb) / hb.mem_total_mb : null;
      return [
        { label: 'CPU', pct: hb.cpu_percent ?? 0, text: hb.cpu_percent == null ? '—' : `${Math.round(hb.cpu_percent)}%`, band: band('cpu', hb.cpu_percent) },
        { label: 'TEMP', pct: hb.temp_c == null ? 0 : (100 * hb.temp_c) / TEMP_MAX, text: hb.temp_c == null ? '—' : `${Math.round(hb.temp_c)}°`, band: band('temp', hb.temp_c) },
        { label: 'MEM', pct: memPct ?? 0, text: memPct == null ? '—' : `${Math.round(memPct)}%`, band: band('mem', memPct) },
      ];
    },

    // ---- sheets -----------------------------------------------------------
    get sheetTitle() { return this.shownSheet === 'modules' ? 'MODULES' : 'DEVICES'; },
    openSheet(name) {
      this.sheet = this.sheet === name ? null : name;
      if (this.sheet) {
        this.shownSheet = this.sheet;
        this.$nextTick(() => this.$refs.sheetClose?.focus());
      }
      this.poke();
      this.saveSheet();
    },
    closeSheet() { this.sheet = null; this.saveSheet(); },
    saveSheet() {
      try {
        if (this.sheet) localStorage.setItem(SHEET_KEY, this.sheet);
        else localStorage.removeItem(SHEET_KEY);
      } catch { /* private mode etc. — the sheet just isn't remembered */ }
    },
    poke() { this.idleAt = Date.now(); },
    swipeStart(e) { this.touchY = e.touches[0].clientY; },
    swipeEnd(e) {
      if (this.touchY != null && e.changedTouches[0].clientY - this.touchY > SWIPE_CLOSE_PX) this.closeSheet();
      this.touchY = null;
    },
  };
}
