/* Contact merge — checkbox tracking for the contacts list */
(function () {
  var selectedIds = new Set();

  function bindCheckboxes() {
    var selectAll = document.getElementById("select-all");
    var checks = document.querySelectorAll(".contact-check");

    // Restore checked state after HTMX swap
    checks.forEach(function (cb) {
      cb.checked = selectedIds.has(cb.value);
      cb.addEventListener("change", function () {
        if (cb.checked) {
          selectedIds.add(cb.value);
        } else {
          selectedIds.delete(cb.value);
        }
        updateToolbar();
      });
    });

    if (selectAll) {
      selectAll.addEventListener("change", function () {
        checks.forEach(function (cb) {
          cb.checked = selectAll.checked;
          if (selectAll.checked) {
            selectedIds.add(cb.value);
          } else {
            selectedIds.delete(cb.value);
          }
        });
        updateToolbar();
      });
    }

    updateToolbar();
  }

  function updateToolbar() {
    var toolbar = document.getElementById("merge-toolbar");
    var countEl = document.getElementById("merge-count");
    if (!toolbar) return;
    if (selectedIds.size >= 2) {
      toolbar.style.display = "";
      if (countEl) countEl.textContent = selectedIds.size;
    } else {
      toolbar.style.display = "none";
    }
  }

  window.mergeSelected = function () {
    if (selectedIds.size < 2) return;
    var params = Array.from(selectedIds)
      .map(function (id) {
        return "ids=" + encodeURIComponent(id);
      })
      .join("&");
    window.location.href = "/contacts/merge?" + params;
  };

  // Bind on initial load
  document.addEventListener("DOMContentLoaded", bindCheckboxes);
  // Re-bind after HTMX swaps
  document.body.addEventListener("htmx:afterSettle", bindCheckboxes);
})();
