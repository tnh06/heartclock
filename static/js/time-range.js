/*
 * Optional start and end times on the add and edit date forms.
 *
 * The visible time boxes are in the person's own timezone. On submit they are
 * converted to UTC timestamps and put in the hidden started_at and ended_at
 * fields, which is what the server stores.
 */
(function () {
    const form = document.getElementById('date-form');
    if (!form) return;

    const dateInput = form.elements['date'];
    const startInput = form.elements['start_time'];
    const endInput = form.elements['end_time'];
    const startedAt = form.elements['started_at'];
    const endedAt = form.elements['ended_at'];

    const DAY_MS = 24 * 60 * 60 * 1000;
    const pad = n => String(n).padStart(2, '0');
    const toTimeValue = date => `${pad(date.getHours())}:${pad(date.getMinutes())}`;
    const snapshot = () => [dateInput.value, startInput.value, endInput.value].join('|');

    // Edit page: show the saved UTC times as local times
    if (startedAt.value && endedAt.value) {
        startInput.value = toTimeValue(new Date(startedAt.value));
        endInput.value = toTimeValue(new Date(endedAt.value));
    }

    const initial = snapshot();

    // If one time is filled in, the other becomes required
    function updateRequired() {
        const eitherFilled = Boolean(startInput.value || endInput.value);
        startInput.required = eitherFilled;
        endInput.required = eitherFilled;
    }

    startInput.addEventListener('input', updateRequired);
    endInput.addEventListener('input', updateRequired);
    updateRequired();

    form.addEventListener('submit', () => {
        // Nothing changed, so keep the saved values exactly as they are
        if (snapshot() === initial) return;

        if (!startInput.value || !endInput.value) {
            startedAt.value = '';
            endedAt.value = '';
            return;
        }

        const start = new Date(`${dateInput.value}T${startInput.value}`);
        let end = new Date(`${dateInput.value}T${endInput.value}`);

        // An end time earlier than the start means the date ran past midnight
        if (end <= start) end = new Date(end.getTime() + DAY_MS);

        startedAt.value = start.toISOString();
        endedAt.value = end.toISOString();
    });
})();