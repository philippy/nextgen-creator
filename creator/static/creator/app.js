const firstError = document.querySelector(".invalid input, .invalid select, .invalid textarea, .field-errors");
if (firstError) firstError.focus();

const editor = document.querySelector("[data-script-editor]");
if (editor) {
  const previewButton = editor.querySelector("[data-preview]");
  const preview = editor.querySelector("[data-preview-content]");
  const previewError = editor.querySelector("[data-preview-error]");
  const body = editor.elements.body;
  let dirty = false;
  editor.addEventListener("input", () => { dirty = true; });
  editor.addEventListener("submit", () => { dirty = false; });
  window.addEventListener("beforeunload", (event) => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = true;
    }
  });
  previewButton.hidden = false;
  previewButton.addEventListener("click", async () => {
    previewError.hidden = true;
    if (!preview.hidden) {
      preview.hidden = true;
      body.hidden = false;
      previewButton.textContent = "Prévia";
      previewButton.setAttribute("aria-pressed", "false");
      body.focus();
      return;
    }
    previewButton.disabled = true;
    try {
      const data = new URLSearchParams();
      data.set("body", body.value);
      data.set("csrfmiddlewaretoken", editor.elements.csrfmiddlewaretoken.value);
      const response = await fetch(editor.dataset.previewUrl, { method: "POST", body: data });
      if (!response.ok || response.redirected) throw new Error("Falha na prévia");
      preview.innerHTML = await response.text();
      if (!preview.textContent.trim()) preview.textContent = "Nenhum texto para visualizar.";
      body.hidden = true;
      body.after(preview);
      preview.hidden = false;
      previewButton.textContent = "Editar texto";
      previewButton.setAttribute("aria-pressed", "true");
    } catch {
      previewError.textContent = "Não foi possível gerar a prévia. Tente novamente.";
      previewError.hidden = false;
    } finally {
      previewButton.disabled = false;
    }
  });
}
