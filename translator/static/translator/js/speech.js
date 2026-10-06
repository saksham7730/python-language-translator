// US-11: Listen (text-to-speech) and Copy buttons.
// Any button with data-speak="#id" reads that element's text aloud in the language data-lang.
// Any button with data-copy="#id" copies that element's text to the clipboard.
// Text-to-speech uses the browser's built-in Web Speech API: free, no API key, works offline.
(function () {
  // Google uses a few old/odd codes; the browser expects standard BCP-47 tags
  const BCP47 = { iw: "he", jw: "jv", "zh-CN": "zh-CN", "zh-TW": "zh-TW", "mni-Mtei": "mni" };

  function textOf(selector) {
    const el = document.querySelector(selector);
    return el ? (el.value !== undefined ? el.value : el.textContent).trim() : "";
  }

  // ---------- Listen ----------
  const speakButtons = document.querySelectorAll("[data-speak]");
  const synth = window.speechSynthesis;

  if (!synth) {
    speakButtons.forEach((b) => b.remove());   // browser has no text-to-speech at all
  } else {
    function voiceFor(lang) {
      const tag = (BCP47[lang] || lang).toLowerCase();
      const base = tag.split("-")[0];
      const voices = synth.getVoices();
      return voices.find((v) => v.lang.toLowerCase() === tag)
          || voices.find((v) => v.lang.toLowerCase().split(/[-_]/)[0] === base);
    }

    // Voices load asynchronously in some browsers, so check again when they arrive
    function updateAvailability() {
      if (synth.getVoices().length === 0) return;   // not loaded yet: leave buttons enabled
      speakButtons.forEach((button) => {
        const available = Boolean(voiceFor(button.dataset.lang));
        button.disabled = !available;
        button.title = available ? "Listen" : "No voice for this language on this device";
      });
    }
    updateAvailability();
    synth.addEventListener?.("voiceschanged", updateAvailability);

    speakButtons.forEach((button) => {
      button.addEventListener("click", () => {
        if (synth.speaking) {          // second click stops speaking
          synth.cancel();
          return;
        }
        const utterance = new SpeechSynthesisUtterance(textOf(button.dataset.speak));
        utterance.lang = BCP47[button.dataset.lang] || button.dataset.lang;
        const voice = voiceFor(button.dataset.lang);
        if (voice) utterance.voice = voice;
        synth.speak(utterance);
      });
    });
  }

  // ---------- Copy ----------
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(textOf(button.dataset.copy));
        button.textContent = "✓";
      } catch (e) {
        button.textContent = "✗";      // clipboard blocked (e.g. not on localhost / https)
      }
      setTimeout(() => (button.textContent = "📋"), 1500);
    });
  });
})();
