(function () {
    const form = document.getElementById('date-form');
    if (!form) return;

    const dateEl = form.elements['date'];
    const startEl = form.elements['start_time'];
    const endEl = form.elements['end_time'];
    const startedAt = form.elements['started_at'];
    const endedAt = form.elements['ended_at'];

    const pad = n => String(n).padStart(2, '0');
    const hhmm = d => `${pad(d.getHours())}:${pad(d.getMinutes())}`;

    // Edit page: fill the time inputs from the stored UTC times
    if (startedAt.value && endedAt.value) {
        startEl.value = hhmm(new Date(startedAt.value));
        endEl.value = hhmm(new Date(endedAt.value));
    }

    const initial = [dateEl.value, startEl.value, endEl.value].join('|');

    // If one time is filled in, the other becomes required
    function sync() {
        const either = startEl.value || endEl.value;
        startEl.required = endEl.required = Boolean(either);
    }
    startEl.addEventListener('input', sync);
    endEl.addEventListener('input', sync);
    sync();

    form.addEventListener('submit', () => {
        const current = [dateEl.value, startEl.value, endEl.value].join('|');
        if (current === initial) return; // nothing changed, keep the stored values

        if (!startEl.value || !endEl.value) {
            startedAt.value = '';
            endedAt.value = '';
            return;
        }

        const start = new Date(`${dateEl.value}T${startEl.value}`);
        let end = new Date(`${dateEl.value}T${endEl.value}`);
        if (end <= start) end = new Date(end.getTime() + 24 * 60 * 60 * 1000); // ran past midnight
        startedAt.value = start.toISOString();
        endedAt.value = end.toISOString();
    });
})();