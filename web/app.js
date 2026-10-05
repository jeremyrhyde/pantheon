/* Pantheon UI — Alpine.js component state for index.html (x-data="app()").
 * Placeholder home screen: one tile per registered module. All URLs are
 * relative, so this works at :8010/ and behind the gateway at :8000/. */

function app() {
  return {
    tab: 'home',
    healthy: false,
    modules: [],

    async init() {
      await this.refresh();
      setInterval(() => this.refresh(), 10_000);
    },

    async refresh() {
      try {
        const [health, modules] = await Promise.all([fetch('health'), fetch('api/modules/')]);
        this.healthy = health.ok;
        if (modules.ok) this.modules = await modules.json();
      } catch {
        this.healthy = false;
      }
    },
  };
}
