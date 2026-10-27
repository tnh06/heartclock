(function () {
    const images = Array.from(document.querySelectorAll('img[data-group]'));
    if (!images.length) return;

    const overlay = document.createElement('div');
    overlay.className = 'viewer';
    overlay.hidden = true;
    overlay.innerHTML = `
        <button class="viewer-close" aria-label="Close">&times;</button>
        <button class="viewer-prev" aria-label="Previous">&#8249;</button>
        <img class="viewer-img" alt="">
        <button class="viewer-next" aria-label="Next">&#8250;</button>
        <div class="viewer-count"></div>`;
    document.body.appendChild(overlay);

    const big = overlay.querySelector('.viewer-img');
    const count = overlay.querySelector('.viewer-count');
    let group = [];
    let index = 0;

    function show() {
        big.src = group[index].src;
        big.alt = group[index].alt;
        count.textContent = `${index + 1} / ${group.length}`;
        overlay.classList.toggle('single', group.length < 2);
    }

    function open(img) {
        group = images.filter(i => i.dataset.group === img.dataset.group);
        index = group.indexOf(img);
        show();
        overlay.hidden = false;
        document.body.style.overflow = 'hidden';
    }

    function close() {
        overlay.hidden = true;
        big.removeAttribute('src');
        document.body.style.overflow = '';
    }

    function step(n) {
        index = (index + n + group.length) % group.length;
        show();
    }

    images.forEach(img => img.addEventListener('click', e => {
        e.preventDefault();
        open(img);
    }));

    overlay.querySelector('.viewer-close').addEventListener('click', close);
    overlay.querySelector('.viewer-prev').addEventListener('click', () => step(-1));
    overlay.querySelector('.viewer-next').addEventListener('click', () => step(1));
    overlay.addEventListener('click', e => { if (e.target === overlay) close(); });

    document.addEventListener('keydown', e => {
        if (overlay.hidden) return;
        if (e.key === 'Escape') close();
        if (e.key === 'ArrowLeft') step(-1);
        if (e.key === 'ArrowRight') step(1);
    });

    let startX = null;
    overlay.addEventListener('touchstart', e => { startX = e.touches[0].clientX; }, { passive: true });
    overlay.addEventListener('touchend', e => {
        if (startX === null) return;
        const dx = e.changedTouches[0].clientX - startX;
        startX = null;
        if (Math.abs(dx) > 50 && group.length > 1) step(dx < 0 ? 1 : -1);
    });
})();