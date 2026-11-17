(() => {
  'use strict';
  const link = document.getElementById('enrollment-maintenance-entry');
  if (!link) return;
  let reviewing = false;
  link.addEventListener('click', async event => {
    event.preventDefault();
    if (reviewing) return;
    if (!window.Swal) {
      const error = document.getElementById('enrollment-entry-error');
      error.hidden = false;
      error.textContent = 'The maintenance confirmation could not load. Reload the page to continue.';
      return;
    }
    reviewing = true;
    try {
      const result = await Swal.fire({
        title: 'Open enrollment maintenance?',
        text: 'This admin area exports personal data, imports enrollments and can reset enrolled data. Running an operation pauses registration. Continue only for planned maintenance.',
        icon: 'info', showCancelButton: true, confirmButtonText: 'Open maintenance',
        cancelButtonText: 'Stay on home', reverseButtons: true, focusCancel: true,
        allowEnterKey: false, width: 560, customClass: {popup: 'enrollment-confirm'},
        didOpen: () => Swal.getCancelButton().focus()
      });
      if (result.isConfirmed) window.location.assign(link.href);
    } finally { reviewing = false; }
  });
})();
