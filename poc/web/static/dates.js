(function () {
  "use strict";

  var meta = document.querySelector('meta[name="crm-timezone"]');
  var tz = meta ? meta.content : "UTC";

  var dtFmt = new Intl.DateTimeFormat(undefined, {
    timeZone: tz,
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

  var dateFmt = new Intl.DateTimeFormat(undefined, {
    timeZone: tz,
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  function formatTimeElements(root) {
    var els = (root || document).querySelectorAll("time[data-format]:not([data-formatted])");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var iso = el.getAttribute("datetime");
      if (!iso) continue;
      try {
        var d = new Date(iso);
        if (isNaN(d.getTime())) continue;
        var fmt = el.getAttribute("data-format") === "date" ? dateFmt : dtFmt;
        el.textContent = fmt.format(d);
        el.setAttribute("data-formatted", "1");
      } catch (e) {
        // leave fallback text
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    formatTimeElements();
  });

  document.addEventListener("htmx:afterSettle", function (event) {
    formatTimeElements(event.detail.elt);
  });
})();
