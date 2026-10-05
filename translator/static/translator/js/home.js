// Small enhancements for the translator card on the home page.
(function () {
  const source = document.getElementById("source-text");
  const output = document.getElementById("output-text");
  const counter = document.getElementById("char-count");
  const sourceLang = document.getElementById("source-lang");
  const targetLang = document.getElementById("target-lang");
  const swapBtn = document.getElementById("swap-btn");

  // Live character counter (the 5000 limit matches the translation API's limit)
  function updateCount() {
    counter.textContent = source.value.length;
  }
  source.addEventListener("input", updateCount);
  updateCount();

  // Swap languages (and texts). If the source is "Auto-detect" there is nothing
  // sensible to swap into the target, so we only swap when a real language is chosen.
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
})();
