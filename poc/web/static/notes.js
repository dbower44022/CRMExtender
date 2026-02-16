/**
 * Notes editor — Tiptap rich-text integration with HTMX.
 *
 * Initializes Tiptap editors for .note-editor elements, syncs content
 * to hidden form fields, handles image paste/drop upload, and
 * re-initializes after HTMX swaps.
 */

let tiptapLoaded = false;
let modules = {};

async function loadTiptap() {
  if (tiptapLoaded) return modules;
  try {
    const [core, starterKit, image, link, placeholder, mention] = await Promise.all([
      import("@tiptap/core"),
      import("@tiptap/starter-kit"),
      import("@tiptap/extension-image"),
      import("@tiptap/extension-link"),
      import("@tiptap/extension-placeholder"),
      import("@tiptap/extension-mention"),
    ]);
    modules = { Editor: core.Editor, StarterKit: starterKit.default || starterKit.StarterKit,
                Image: image.default || image.Image,
                Link: link.default || link.Link,
                Placeholder: placeholder.default || placeholder.Placeholder,
                Mention: mention.default || mention.Mention };
    tiptapLoaded = true;
    return modules;
  } catch (err) {
    console.warn("Tiptap failed to load, falling back to textarea:", err);
    return null;
  }
}

/** Upload a file and return {url, id} */
async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/notes/upload", { method: "POST", body: form });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.error || "Upload failed");
  }
  return resp.json();
}

/** Create toolbar buttons */
function buildToolbar(editor) {
  const bar = document.createElement("div");
  bar.className = "note-editor-toolbar";

  const btn = (label, title, action, activeCheck) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.title = title;
    b.addEventListener("click", (e) => { e.preventDefault(); action(); });
    if (activeCheck) {
      editor.on("selectionUpdate", () => b.classList.toggle("is-active", activeCheck()));
      editor.on("transaction", () => b.classList.toggle("is-active", activeCheck()));
    }
    return b;
  };

  const sep = () => { const s = document.createElement("span"); s.className = "separator"; return s; };

  bar.append(
    btn("B", "Bold", () => editor.chain().focus().toggleBold().run(),
        () => editor.isActive("bold")),
    btn("I", "Italic", () => editor.chain().focus().toggleItalic().run(),
        () => editor.isActive("italic")),
    btn("S", "Strikethrough", () => editor.chain().focus().toggleStrike().run(),
        () => editor.isActive("strike")),
    btn("Code", "Inline code", () => editor.chain().focus().toggleCode().run(),
        () => editor.isActive("code")),
    sep(),
    btn("H1", "Heading 1", () => editor.chain().focus().toggleHeading({ level: 1 }).run(),
        () => editor.isActive("heading", { level: 1 })),
    btn("H2", "Heading 2", () => editor.chain().focus().toggleHeading({ level: 2 }).run(),
        () => editor.isActive("heading", { level: 2 })),
    btn("H3", "Heading 3", () => editor.chain().focus().toggleHeading({ level: 3 }).run(),
        () => editor.isActive("heading", { level: 3 })),
    sep(),
    btn("\u2022", "Bullet list", () => editor.chain().focus().toggleBulletList().run(),
        () => editor.isActive("bulletList")),
    btn("1.", "Ordered list", () => editor.chain().focus().toggleOrderedList().run(),
        () => editor.isActive("orderedList")),
    btn("\u201C", "Blockquote", () => editor.chain().focus().toggleBlockquote().run(),
        () => editor.isActive("blockquote")),
    btn("---", "Horizontal rule", () => editor.chain().focus().setHorizontalRule().run()),
    sep(),
    btn("\uD83D\uDDBC", "Insert image URL", () => {
      const url = prompt("Image URL:");
      if (url) editor.chain().focus().setImage({ src: url }).run();
    }),
    btn("\uD83D\uDD17", "Insert link", () => {
      const url = prompt("Link URL:");
      if (url) editor.chain().focus().setLink({ href: url }).run();
      else editor.chain().focus().unsetLink().run();
    }),
  );

  return bar;
}

/** Initialize a Tiptap editor on an element */
function initEditor(el) {
  if (el._tiptapEditor) return;
  if (!modules.Editor) return;

  const editorId = el.dataset.editor;
  const wrapper = el.closest(".note-editor-wrapper");
  const jsonInput = wrapper.querySelector(`[name="content_json"]`);
  const htmlInput = wrapper.querySelector(`[name="content_html"]`);

  // Load existing content — prefer JSON, fall back to HTML
  let initialContent = "";
  if (el.dataset.content) {
    try { initialContent = JSON.parse(el.dataset.content); } catch { initialContent = ""; }
  }
  if (!initialContent && el.dataset.contentHtml) {
    initialContent = el.dataset.contentHtml;
  }

  const mentionSuggestion = {
    items: async ({ query }) => {
      if (!query || query.length < 1) return [];
      try {
        const resp = await fetch(`/notes/mentions?q=${encodeURIComponent(query)}&type=user`);
        return resp.ok ? await resp.json() : [];
      } catch { return []; }
    },
    render: () => {
      let popup, items = [];
      return {
        onStart: (props) => {
          popup = document.createElement("div");
          popup.className = "mention-popup";
          popup.style.cssText = "position:absolute;background:var(--pico-card-background-color);border:1px solid var(--pico-muted-border-color);border-radius:4px;padding:4px;z-index:999;max-height:200px;overflow-y:auto;";
          document.body.appendChild(popup);
          items = props.items;
          renderItems(popup, items, props);
          positionPopup(popup, props);
        },
        onUpdate: (props) => {
          items = props.items;
          renderItems(popup, items, props);
          positionPopup(popup, props);
        },
        onKeyDown: (props) => {
          if (props.event.key === "Escape") { popup?.remove(); return true; }
          return false;
        },
        onExit: () => { popup?.remove(); },
      };
    },
  };

  function renderItems(popup, items, props) {
    popup.innerHTML = "";
    if (!items.length) {
      popup.innerHTML = "<div style='padding:4px 8px;color:var(--pico-muted-color);font-size:.85em;'>No results</div>";
      return;
    }
    items.forEach((item, i) => {
      const div = document.createElement("div");
      div.style.cssText = "padding:4px 8px;cursor:pointer;font-size:.9em;";
      div.textContent = item.name || item.id;
      div.addEventListener("mouseenter", () => div.style.background = "var(--pico-secondary-background)");
      div.addEventListener("mouseleave", () => div.style.background = "");
      div.addEventListener("click", () => props.command({ id: item.id, label: item.name }));
      popup.appendChild(div);
    });
  }

  function positionPopup(popup, props) {
    if (!props.clientRect) return;
    const rect = props.clientRect();
    if (!rect) return;
    popup.style.left = rect.left + "px";
    popup.style.top = (rect.bottom + 4) + "px";
  }

  const extensions = [
    modules.StarterKit,
    modules.Image.configure({ inline: true, allowBase64: false }),
    modules.Link.configure({ openOnClick: false }),
    modules.Placeholder.configure({ placeholder: "Write your note..." }),
    modules.Mention.configure({
      HTMLAttributes: { class: "mention" },
      suggestion: mentionSuggestion,
      renderLabel: ({ node }) => `@${node.attrs.label || node.attrs.id}`,
    }),
  ];

  const editor = new modules.Editor({
    element: el,
    extensions,
    content: initialContent || "",
    onUpdate: ({ editor: ed }) => {
      if (jsonInput) jsonInput.value = JSON.stringify(ed.getJSON());
      if (htmlInput) htmlInput.value = ed.getHTML();
    },
  });

  // Build and insert toolbar
  const toolbar = buildToolbar(editor);
  el.parentNode.insertBefore(toolbar, el);

  // Image paste/drop upload
  el.addEventListener("paste", async (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        e.preventDefault();
        const file = item.getAsFile();
        try {
          const result = await uploadFile(file);
          editor.chain().focus().setImage({ src: result.url }).run();
        } catch (err) {
          console.error("Paste upload failed:", err);
        }
        return;
      }
    }
  });

  el.addEventListener("drop", async (e) => {
    const files = e.dataTransfer?.files;
    if (!files?.length) return;
    for (const file of files) {
      if (file.type.startsWith("image/")) {
        e.preventDefault();
        try {
          const result = await uploadFile(file);
          editor.chain().focus().setImage({ src: result.url }).run();
        } catch (err) {
          console.error("Drop upload failed:", err);
        }
        return;
      }
    }
  });

  // Initial sync
  if (jsonInput) jsonInput.value = JSON.stringify(editor.getJSON());
  if (htmlInput) htmlInput.value = editor.getHTML();

  el._tiptapEditor = editor;
}

/** Find and init all uninitialized editors on the page */
function initAllEditors() {
  document.querySelectorAll(".note-editor:not([data-initialized])").forEach((el) => {
    el.dataset.initialized = "true";
    initEditor(el);
  });
}

// Initialize on page load
loadTiptap().then(() => initAllEditors());

// Re-initialize after HTMX swaps
document.body.addEventListener("htmx:afterSwap", () => {
  if (tiptapLoaded) initAllEditors();
});
document.body.addEventListener("htmx:afterSettle", () => {
  if (tiptapLoaded) initAllEditors();
});
