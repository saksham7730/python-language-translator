// Small enhancements for the translator card on the home page.
// The page works without this file; JavaScript only makes it nicer to use.
(function () {
  const form = document.getElementById("translate-form");
  const source = document.getElementById("source-text");
  const output = document.getElementById("output-text");
  const counter = document.getElementById("char-count");
  const sourceLang = document.getElementById("source-lang");
  const targetLang = document.getElementById("target-lang");
  const swapBtn = document.getElementById("swap-btn");
  const translateBtn = document.getElementById("translate-btn");

  // Live character counter (the 5000 limit matches the translation API's limit)
  function updateCount() {
    counter.textContent = source.value.length;
  }
  source.addEventListener("input", updateCount);
  updateCount();

  // Swap languages (and texts). If the source is "Auto-detect" there is nothing
  // sensible to put in the target, so we only swap when a real language is chosen.
  swapBtn.addEventListener("click", function () {
    if (sourceLang.value === "auto") {
      swapBtn.title = "Choose a source language first";
      return;
    }
    [sourceLang.value, targetLang.value] = [targetLang.value, sourceLang.value];
    if (output.value) {
      [source.value, output.value] = [output.value, source.value];
      updateCount();
    }
  });

  // Ctrl+Enter (Cmd+Enter on Mac) submits the form from the text box
  source.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      form.requestSubmit();
    }
  });

  // While the request is running: show a spinner and block double-submits
  form.addEventListener("submit", function () {
    translateBtn.disabled = true;
    translateBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Translating…';
  });

  // If the user comes back with the browser's Back button, the page may be restored
  // from cache with the button still disabled, so reset it.
  window.addEventListener("pageshow", function () {
    translateBtn.disabled = false;
    translateBtn.textContent = "Translate";
  });
})();
