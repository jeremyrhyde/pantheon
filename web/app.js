/* Pantheon home screen — the modules floating in a starfield.
 * Everything comes from api/overview (relative, so this page works at :8010/
 * and behind the gateway at :8000/); `from=home` tells the access log this
 * screen apart from the status screen. */

const HOME_POLL_MS = 10_000;

// The leave duration lives in style.css as --duration-leave.
function leaveMs() {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--duration-leave').trim();
  const n = parseFloat(raw);
  if (!Number.isFinite(n)) return 400;
  return raw.endsWith('ms') ? n : raw.endsWith('s') ? n * 1000 : n;
}

function homeApp() {
  return {
    modules: [],
    overall: 'offline',
    loaded: false,
    broken: {},
    chosen: null,
    leaving: false,
    clock: '',
    date: '',

    init() {
      startStarfield(this.$refs.sky, { dim: 1, speed: 1 });
      this.tick();
      setInterval(() => this.tick(), 1000);
      this.refresh();
      setInterval(() => this.refresh(), HOME_POLL_MS);
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) this.refresh();
      });
      // Coming back with the browser's Back button restores this page as it
      // was left — mid-zoom. Reset it.
      window.addEventListener('pageshow', (e) => {
        if (e.persisted) { this.leaving = false; this.chosen = null; }
      });
    },

    tick() {
      const now = new Date();
      this.clock = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      this.date = now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
    },

    async refresh() {
      if (document.hidden) return;
      try {
        const res = await fetch('api/overview?from=home');
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        this.overall = data.overall;
        this.modules = data.modules.map((m) => ({ ...m, icon: `api/modules/${m.name}/icon` }));
      } catch {
        this.overall = 'offline';
      } finally {
        this.loaded = true;
      }
    },

    open(m) {
      if (!m.enabled || this.leaving) return;
      this.chosen = m.name;
      this.leaving = true;
      setTimeout(() => { window.location.href = m.path; }, leaveMs());
    },
  };
}
