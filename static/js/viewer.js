/*
 * Full-screen photo viewer.
 *
 * Any <img data-group="..."> opens the viewer when tapped. Photos that share
 * the same data-group value can be browsed with the arrows, the keyboard
 * (left, right and Escape) or a swipe.
 */
(function () {
    const thumbnails = Array.from(document.querySelectorAll('img[data-group]'));
    if (!thumbnails.length) return;

    const SWIPE_DISTANCE = 50;

    const overlay = document.createElement('div');
    overlay.className = 'viewer';
    overlay.hidden = true;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Photo viewer');
    overlay.innerHTML = `
        <button class="viewer-close" aria-label="Close">&times;</button>
        <button class="viewer-prev" aria-label="Previous photo">&#8249;</button>
        <img class="viewer-img" alt="">
        <button class="viewer-next" aria-label="Next photo">&#8250;</button>
        <div class="viewer-count"></div>`;
    document.body.appendChild(overlay);

    const bigImage = overlay.querySelector('.viewer-img');
    const counter = overlay.querySelector('.viewer-count');
    const closeButton = overlay.querySelector('.viewer-close');

    let photos = [];
    let current = 0;
    let opener = null;
    let touchStartX = null;

    function render() {
        bigImage.src = photos[current].src;
        bigImage.alt = photos[current].alt;
        counter.textContent = `${current + 1} / ${photos.length}`;
        overlay.classList.toggle('single', photos.length < 2);
    }

    function open(thumbnail) {
        photos = thumbnails.filter(img => img.dataset.group === thumbnail.dataset.group);
        current = photos.indexOf(thumbnail);
        opener = thumbnail;
        render();
        overlay.hidden = false;
        document.body.style.overflow = 'hidden';
        closeButton.focus();
    }

    function close() {
        overlay.hidden = true;
        bigImage.removeAttribute('src');
        document.body.style.overflow = '';
        if (opener) opener.focus({ preventScroll: true });
    }

    function step(direction) {
        current = (current + direction + photos.length) % photos.length;
        render();
    }

    thumbnails.forEach(thumbnail => {
        thumbnail.addEventListener('click', event => {
            event.preventDefault();
            open(thumbnail);
        });
    });

    closeButton.addEventListener('click', close);
    overlay.querySelector('.viewer-prev').addEventListener('click', () => step(-1));
    overlay.querySelector('.viewer-next').addEventListener('click', () => step(1));

    // Tapping the dark area closes the viewer
    overlay.addEventListener('click', event => {
        if (event.target === overlay) close();
    });

    document.addEventListener('keydown', event => {
        if (overlay.hidden) return;
        if (event.key === 'Escape') close();
        if (event.key === 'ArrowLeft') step(-1);
        if (event.key === 'ArrowRight') step(1);
    });

    overlay.addEventListener('touchstart', event => {
        touchStartX = event.touches[0].clientX;
    }, { passive: true });

    overlay.addEventListener('touchend', event => {
        if (touchStartX === null) return;
        const distance = event.changedTouches[0].clientX - touchStartX;
        touchStartX = null;
        if (Math.abs(distance) > SWIPE_DISTANCE && photos.length > 1) {
            step(distance < 0 ? 1 : -1);
        }
    });
})();