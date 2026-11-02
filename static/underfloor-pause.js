window.setupUnderfloorPause = function setupUnderfloorPause(socket, inactivityMinutes) {
    const overlay = document.getElementById('ufPauseOverlay');
    if (!overlay || inactivityMinutes <= 0) return;

    const slides = Array.from(overlay.querySelectorAll('.uf-pause-slide'));
    const imageDurationMs = 10000;
    const transitionMs = 650;
    const noSerialTimeoutMs = 10000;
    const unchangedTimeoutMs = inactivityMinutes * 60000;
    let images = [];
    let loading = false;
    let retryAfter = 0;
    let active = false;
    let reason = '';
    let generation = 0;
    let visibleSlide = 0;
    let visibleIndex = -1;
    let nextTimer = null;
    let cleanupTimer = null;
    let lastDataAt = Date.now();
    let lastChangeAt = Date.now();
    let scoreSignature = null;
    const competitorSignatures = {};

    function imageUrl(src) {
        return `url(${JSON.stringify(src)})`;
    }

    function preload(src) {
        return new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = resolve;
            image.onerror = reject;
            image.src = src;
        });
    }

    function hide() {
        generation += 1;
        active = false;
        reason = '';
        visibleIndex = -1;
        clearTimeout(nextTimer);
        clearTimeout(cleanupTimer);
        overlay.hidden = true;
        slides.forEach((slide) => {
            slide.style.transition = 'none';
            slide.style.transform = 'translateY(100%)';
            slide.style.backgroundImage = 'none';
        });
    }

    function currentImageIndex() {
        // Tutte e quattro le finestre usano lo stesso orologio per cambiare insieme.
        return Math.floor(Date.now() / imageDurationMs) % images.length;
    }

    function scheduleNext() {
        clearTimeout(nextTimer);
        if (!active) return;
        const delay = imageDurationMs - (Date.now() % imageDurationMs) + 10;
        nextTimer = setTimeout(async () => {
            await advance();
            scheduleNext();
        }, delay);
    }

    async function advance() {
        if (!active || images.length < 2) return;
        const index = currentImageIndex();
        if (index === visibleIndex) return;
        const token = generation;
        try {
            await preload(images[index]);
        } catch (_) {
            return;
        }
        if (!active || token !== generation) return;

        clearTimeout(cleanupTimer);
        const outgoing = slides[visibleSlide];
        const incoming = slides[1 - visibleSlide];
        incoming.style.transition = 'none';
        incoming.style.transform = 'translateY(100%)';
        incoming.style.backgroundImage = imageUrl(images[index]);
        incoming.style.zIndex = '2';
        outgoing.style.zIndex = '1';
        void incoming.offsetHeight;
        requestAnimationFrame(() => {
            if (!active || token !== generation) return;
            const transition = `transform ${transitionMs}ms ease-in-out`;
            incoming.style.transition = transition;
            outgoing.style.transition = transition;
            incoming.style.transform = 'translateY(0)';
            outgoing.style.transform = 'translateY(-100%)';
        });
        visibleSlide = 1 - visibleSlide;
        visibleIndex = index;
        cleanupTimer = setTimeout(() => {
            if (!active || token !== generation) return;
            outgoing.style.transition = 'none';
            outgoing.style.transform = 'translateY(100%)';
            outgoing.style.backgroundImage = 'none';
        }, transitionMs + 50);
    }

    function stillInactive(pauseReason) {
        const now = Date.now();
        return pauseReason === 'no_serial'
            ? now - lastDataAt > noSerialTimeoutMs
            : now - lastDataAt <= noSerialTimeoutMs && now - lastChangeAt > unchangedTimeoutMs;
    }

    async function show(pauseReason) {
        if (active || loading || Date.now() < retryAfter) return;
        loading = true;
        const token = generation;
        try {
            if (!images.length) {
                const response = await fetch('/api/pause-videos', { cache: 'no-store' });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const payload = await response.json();
                images = (payload.media || [])
                    .filter((item) => item.type === 'image' && item.underfloorSrc)
                    .map((item) => item.underfloorSrc);
            }
            if (!images.length) {
                retryAfter = Date.now() + 30000;
                return;
            }
            const index = currentImageIndex();
            await preload(images[index]);
            if (token !== generation || !stillInactive(pauseReason)) return;
            visibleSlide = 0;
            visibleIndex = index;
            slides[0].style.transition = 'none';
            slides[0].style.transform = 'translateY(0)';
            slides[0].style.backgroundImage = imageUrl(images[index]);
            slides[0].style.zIndex = '2';
            slides[1].style.zIndex = '1';
            overlay.hidden = false;
            active = true;
            reason = pauseReason;
            scheduleNext();
        } catch (error) {
            retryAfter = Date.now() + 30000;
            console.warn('Immagini pausa sottopedana non disponibili:', error);
        } finally {
            loading = false;
        }
    }

    socket.on('serial_alive', () => {
        lastDataAt = Date.now();
        if (active && reason === 'no_serial') {
            lastChangeAt = lastDataAt;
            hide();
        }
    });

    socket.on('punti_emit', (payload) => {
        const now = Date.now();
        const nextSignature = JSON.stringify(payload?.tabellone || {});
        lastDataAt = now;
        if (scoreSignature !== null && scoreSignature !== nextSignature) {
            lastChangeAt = now;
            hide();
        } else if (scoreSignature === null) {
            lastChangeAt = now;
        } else if (active && reason === 'no_serial') {
            lastChangeAt = now;
            hide();
        }
        scoreSignature = nextSignature;
    });

    socket.on('competitor_emit', (payload) => {
        const competitor = payload?.competitor || payload;
        if (!competitor?.side) return;
        const nextSignature = JSON.stringify([competitor.name, competitor.nation]);
        const previous = competitorSignatures[competitor.side];
        competitorSignatures[competitor.side] = nextSignature;
        lastDataAt = Date.now();
        if (previous === undefined) {
            lastChangeAt = lastDataAt;
            if (active) hide();
        } else if (previous !== nextSignature) {
            lastChangeAt = lastDataAt;
            hide();
        } else if (active && reason === 'no_serial') {
            lastChangeAt = lastDataAt;
            hide();
        }
    });

    setInterval(() => {
        if (active) return;
        const now = Date.now();
        if (now - lastDataAt > noSerialTimeoutMs) {
            show('no_serial');
        } else if (scoreSignature !== null && now - lastChangeAt > unchangedTimeoutMs) {
            show('unchanged');
        }
    }, 1000);
};
