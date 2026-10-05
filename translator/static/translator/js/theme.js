// Light/dark theme toggle.
// Bootstrap 5.3 reads the data-bs-theme attribute on <html> and recolours every component.
// The initial theme is set by the small script in base.html's <head>; this file handles clicks.
(function () {
  const root = document.documentElement;
  const button = document.getElementById("theme-toggle");
  if (!button) return;

  // Show the icon of the theme you would switch TO
  function updateIcon() {
    const isDark = root.getAttribute("data-bs-theme") === "dark";
    button.textContent = isDark ? "☀️" : "🌙";
    button.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
  }

  button.addEventListener("click", function () {
    const next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-bs-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) { /* storage blocked: still works for this page */ }
    updateIcon();
  });

  updateIcon();
})();
