/* Pantheon UI — Alpine.js component state for index.html (x-data="app()"). */

function app() {
  return {
    tab: 'home',
    healthy: false,

    async init() {
      await this.checkHealth();
      setInterval(() => this.checkHealth(), 10_000);
    },

    async checkHealth() {
      try {
        const res = await fetch('/health');
        this.healthy = res.ok;
      } catch {
        this.healthy = false;
      }
    },
  };
}
