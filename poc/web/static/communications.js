/* Communications tab — checkbox tracking, bulk actions, modals */

(function () {
  "use strict";

  var selectedIds = new Set();

  function updateToolbar() {
    var toolbar = document.getElementById("bulk-toolbar");
    var countEl = document.getElementById("selected-count");
    if (!toolbar || !countEl) return;
    countEl.textContent = selectedIds.size;
    toolbar.style.display = selectedIds.size > 0 ? "flex" : "none";
  }

  function bindCheckboxes() {
    var selectAll = document.getElementById("select-all");
    var checkboxes = document.querySelectorAll(".comm-check");

    if (selectAll) {
      selectAll.checked = false;
      selectAll.addEventListener("change", function () {
        checkboxes.forEach(function (cb) {
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

    checkboxes.forEach(function (cb) {
      // Restore checked state after HTMX swap
      if (selectedIds.has(cb.value)) {
        cb.checked = true;
      }
      cb.addEventListener("change", function () {
        if (cb.checked) {
          selectedIds.add(cb.value);
        } else {
          selectedIds.delete(cb.value);
        }
        // Update select-all state
        if (selectAll) {
          selectAll.checked =
            checkboxes.length > 0 &&
            Array.from(checkboxes).every(function (c) { return c.checked; });
        }
        updateToolbar();
      });
    });
  }

  // Build form data with selected IDs + filter state
  function buildFormData() {
    var form = document.getElementById("bulk-form");
    var fd = new FormData();
    selectedIds.forEach(function (id) {
      fd.append("ids", id);
    });
    if (form) {
      new FormData(form).forEach(function (value, key) {
        fd.append(key, value);
      });
    }
    return fd;
  }

  // Bulk archive
  window.bulkArchive = function () {
    if (selectedIds.size === 0) return;
    var fd = buildFormData();
    fetch("/communications/archive", { method: "POST", body: fd })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        document.getElementById("results").innerHTML = html;
        selectedIds.clear();
        updateToolbar();
        bindCheckboxes();
      });
  };

  // Assign to conversation
  window.openAssignModal = function () {
    if (selectedIds.size === 0) return;
    var dialog = document.getElementById("assign-dialog");
    if (dialog) dialog.showModal();
  };

  window.assignToConversation = function (conversationId) {
    var fd = buildFormData();
    fd.append("conversation_id", conversationId);
    fetch("/communications/assign", { method: "POST", body: fd })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        document.getElementById("results").innerHTML = html;
        selectedIds.clear();
        updateToolbar();
        bindCheckboxes();
        var dialog = document.getElementById("assign-dialog");
        if (dialog) dialog.close();
      });
  };

  // Delete conversation
  window.openDeleteModal = function () {
    if (selectedIds.size === 0) return;
    var dialog = document.getElementById("delete-dialog");
    if (dialog) dialog.showModal();
  };

  window.confirmDelete = function () {
    var fd = buildFormData();
    var deleteComms = document.getElementById("delete-comms-too");
    if (deleteComms && deleteComms.checked) {
      fd.append("delete_comms", "true");
    }
    fetch("/communications/delete-conversation", { method: "POST", body: fd })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        document.getElementById("results").innerHTML = html;
        selectedIds.clear();
        updateToolbar();
        bindCheckboxes();
        var dialog = document.getElementById("delete-dialog");
        if (dialog) dialog.close();
      });
  };

  // Sort toggling
  window.toggleSort = function (field) {
    var sortInput = document.querySelector('input[name="sort"]');
    if (!sortInput) return;
    var current = sortInput.value;
    if (current === field) {
      sortInput.value = "-" + field;
    } else if (current === "-" + field) {
      sortInput.value = field;
    } else {
      // Default to descending for date, ascending for others
      sortInput.value = field === "date" ? "-" + field : field;
    }
    // Trigger search via the search input's HTMX
    var searchInput = document.querySelector('.search-bar input[name="q"]');
    if (searchInput) {
      htmx.trigger(searchInput, "search");
    }
  };

  // Dropdown menu toggle
  document.addEventListener("click", function (e) {
    // Toggle dropdown on button click
    var btn = e.target.closest(".dropdown > button");
    if (btn) {
      var menu = btn.nextElementSibling;
      if (menu && menu.classList.contains("dropdown-menu")) {
        menu.classList.toggle("open");
        e.stopPropagation();
        return;
      }
    }
    // Close all dropdowns on outside click
    document.querySelectorAll(".dropdown-menu.open").forEach(function (m) {
      m.classList.remove("open");
    });
  });

  // Re-bind after HTMX swaps
  document.addEventListener("htmx:afterSettle", function (e) {
    if (e.detail.target && e.detail.target.id === "results") {
      bindCheckboxes();
    }
  });

  // Initial bind
  bindCheckboxes();
})();
