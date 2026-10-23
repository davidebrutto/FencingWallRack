(() => {
    function fitMonitor() {
        const scale = Math.min(window.innerWidth / 1536, window.innerHeight / 768);
        document.documentElement.style.setProperty('--monitor-scale', String(scale));
    }

    fitMonitor();
    window.addEventListener('resize', fitMonitor);
})();
