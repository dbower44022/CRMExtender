/* Contact selection — checkbox tracking for the contacts list */
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
    var mergeBtn = document.getElementById("merge-btn");
    var relateBtn = document.getElementById("relate-btn");
    var countEls = document.querySelectorAll(".selected-count");
    if (!toolbar) return;
    if (selectedIds.size >= 1) {
      toolbar.style.display = "";
      countEls.forEach(function (el) { el.textContent = selectedIds.size; });
      if (mergeBtn) mergeBtn.style.display = selectedIds.size >= 2 ? "" : "none";
      if (relateBtn) relateBtn.style.display = "";
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

  window.relateSelected = function () {
    if (selectedIds.size < 1) return;
    var params = Array.from(selectedIds)
      .map(function (id) {
        return "ids=" + encodeURIComponent(id);
      })
      .join("&");
    window.location.href = "/contacts/relate?" + params;
  };

  // Bind on initial load
  document.addEventListener("DOMContentLoaded", bindCheckboxes);
  // Re-bind after HTMX swaps
  document.body.addEventListener("htmx:afterSettle", bindCheckboxes);
})();
