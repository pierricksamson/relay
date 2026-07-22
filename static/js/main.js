document.addEventListener("DOMContentLoaded", () => {
  // --- Onglets de la page /docs (Python / cURL / JavaScript) ---
  document.querySelectorAll("[data-tabs]").forEach((tabs) => {
    const buttons = tabs.querySelectorAll(".tab-btn");
    const panels = tabs.querySelectorAll(".tab-panel");

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.dataset.tab;
        buttons.forEach((b) => b.classList.toggle("active", b === btn));
        panels.forEach((p) => p.classList.toggle("active", p.dataset.panel === target));
      });
    });
  });

  // --- Bouton "Copier" (clé API révélée dans le dashboard) ---
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const value = btn.getAttribute("data-copy");
      try {
        await navigator.clipboard.writeText(value);
        const original = btn.textContent;
        btn.textContent = "Copié !";
        btn.disabled = true;
        setTimeout(() => {
          btn.textContent = original;
          btn.disabled = false;
        }, 1500);
      } catch (err) {
        console.error("Impossible de copier la clé :", err);
      }
    });
  });
});