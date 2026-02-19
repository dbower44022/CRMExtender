/* Inline cell editing for editable grid cells.
   Double-click a td[data-editable] to open an editor. */
(function() {
  'use strict';

  document.addEventListener('dblclick', function(e) {
    var td = e.target.closest('td[data-editable]');
    if (!td || td.classList.contains('editing')) return;

    var entityType = td.dataset.entityType;
    var entityId = td.dataset.entityId;
    var fieldKey = td.dataset.fieldKey;
    var editType = td.dataset.editType || 'text';
    var options = td.dataset.options ? td.dataset.options.split(',') : [];

    // Save original content
    var originalHTML = td.innerHTML;
    var originalText = (td.textContent || '').trim();
    // Treat mdash placeholder as empty
    if (originalText === '\u2014') originalText = '';

    td.classList.add('editing');
    td.innerHTML = '';

    var editor;
    if (editType === 'select' && options.length) {
      editor = document.createElement('select');
      // Add empty option
      var emptyOpt = document.createElement('option');
      emptyOpt.value = '';
      emptyOpt.textContent = '(none)';
      editor.appendChild(emptyOpt);
      options.forEach(function(opt) {
        var o = document.createElement('option');
        o.value = opt;
        o.textContent = opt;
        if (opt === originalText) o.selected = true;
        editor.appendChild(o);
      });
    } else {
      editor = document.createElement('input');
      editor.type = 'text';
      editor.value = originalText;
    }

    editor.style.cssText = 'width:100%;padding:0.15rem 0.3rem;font-size:inherit;margin:0;box-sizing:border-box;';
    td.appendChild(editor);
    editor.focus();
    if (editor.select) editor.select();

    var saving = false;

    function save() {
      if (saving) return;
      saving = true;
      var newValue = editor.value;
      if (newValue === originalText) {
        cancel();
        return;
      }
      fetch('/views/cell-edit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          entity_type: entityType,
          entity_id: entityId,
          field_key: fieldKey,
          value: newValue
        })
      })
      .then(function(resp) { return resp.json().then(function(d) { return {ok: resp.ok, data: d}; }); })
      .then(function(result) {
        td.classList.remove('editing');
        if (result.ok && result.data.ok) {
          var display = result.data.value || '';
          td.textContent = display || '\u2014';
          flash(td, 'rgba(0,180,0,0.15)', 800);
        } else {
          td.innerHTML = originalHTML;
          flash(td, 'rgba(220,0,0,0.15)', 1200);
        }
      })
      .catch(function() {
        td.classList.remove('editing');
        td.innerHTML = originalHTML;
        flash(td, 'rgba(220,0,0,0.15)', 1200);
      });
    }

    function cancel() {
      td.classList.remove('editing');
      td.innerHTML = originalHTML;
      saving = true;
    }

    editor.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); save(); }
      if (e.key === 'Escape') { e.preventDefault(); cancel(); }
    });
    editor.addEventListener('blur', function() {
      // Small delay to allow click events on select options
      setTimeout(function() { if (!saving) save(); }, 150);
    });
  });

  function flash(el, color, duration) {
    el.style.transition = 'background-color 0.2s';
    el.style.backgroundColor = color;
    setTimeout(function() {
      el.style.backgroundColor = '';
      setTimeout(function() { el.style.transition = ''; }, 300);
    }, duration);
  }
})();
