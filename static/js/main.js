let currentTranslations = {};

// ---------------------------------------------------------------------
// i18n : les traductions sont injectées côté serveur dans window.I18N_DATA
// (voir base.html) -> plus de fetch(), application synchrone et immédiate.
// ---------------------------------------------------------------------

function applyLanguage(lang) {
  const dict = (window.I18N_DATA && (window.I18N_DATA[lang] || window.I18N_DATA.fr)) || {};
  currentTranslations = dict;

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    if (dict[key]) element.innerHTML = dict[key];
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    const key = element.dataset.i18nPlaceholder;
    if (dict[key]) element.placeholder = dict[key];
  });

  try {
    localStorage.setItem("app_lang", lang);
  } catch (err) {
    /* stockage indisponible (navigation privée) : pas bloquant */
  }

  // Révèle la page une fois la traduction posée
  document.documentElement.classList.add("i18n-ready");
}

function updateLangUI(lang, flagClass) {
  const currentFlag = document.getElementById("currentFlag");
  const currentLang = document.getElementById("currentLang");
  const options = document.querySelectorAll(".lang-option");

  if (currentFlag) currentFlag.className = `fi ${flagClass}`;
  if (currentLang) currentLang.textContent = lang.toUpperCase();

  options.forEach((opt) => {
    opt.classList.toggle("active", opt.dataset.lang === lang);
  });
}

// Exécuté dès que ce script est atteint : comme il est chargé en fin de
// <body>, tout le DOM existe déjà -> pas besoin d'attendre DOMContentLoaded
// pour poser la traduction le plus tôt possible.
(function initLanguage() {
  let saved = null;
  try {
    saved = localStorage.getItem("app_lang");
  } catch (err) {
    saved = null;
  }

  // Détecte fr, es ou en (défaut: en)
  const browserLang = navigator.language.slice(0, 2);
  const lang = saved || (["fr", "es", "en"].includes(browserLang) ? browserLang : "en");

  // Dictionnaire des drapeaux
  const flagMap = {
    fr: "fi-fr",
    en: "fi-us",
    es: "fi-es"
  };

  updateLangUI(lang, flagMap[lang] || "fi-us");
  applyLanguage(lang);
})();

document.addEventListener("DOMContentLoaded", () => {
  // --- 1. Onglets de la page /docs (Python / cURL / JavaScript) ---
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

  // --- 1bis. Sommaire /docs : suivi de scroll + liens d'ancre copiables ---
  const tocLinks = document.querySelectorAll("[data-toc-link]");
  if (tocLinks.length) {
    const headings = Array.from(tocLinks)
      .map((link) => document.querySelector(link.getAttribute("href")))
      .filter(Boolean);

    const setActive = (id) => {
      tocLinks.forEach((link) => {
        link.classList.toggle("active", link.getAttribute("href") === `#${id}`);
      });
    };

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-90px 0px -70% 0px", threshold: 0 }
    );

    headings.forEach((h) => observer.observe(h));

    if (location.hash) {
      const target = document.querySelector(location.hash);
      if (target) setTimeout(() => target.scrollIntoView({ block: "start" }), 0);
    }
  }

  document.querySelectorAll(".anchor-link[data-anchor]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      const id = btn.dataset.anchor;
      const url = `${location.origin}${location.pathname}#${id}`;
      history.replaceState(null, "", `#${id}`);
      try {
        await navigator.clipboard.writeText(url);
      } catch (err) {
        console.error("Impossible de copier le lien :", err);
      }
      btn.classList.add("copied");
      setTimeout(() => btn.classList.remove("copied"), 1200);
    });
  });

  // --- 2. Bouton "Copier" (clé API révélée dans le dashboard) ---
document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const value = btn.getAttribute("data-copy");
    try {
      await navigator.clipboard.writeText(value);
      const original = btn.textContent;

      const langMessages = {
        fr: "Copié !",
        en: "Copied!",
        es: "¡Copiado!"
      };
      const currentLang = localStorage.getItem("app_lang") || "fr";

      btn.textContent = langMessages[currentLang] || "Copied!";
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

  // --- 3. Sélecteur de langue (interactions) ---
  const toggleBtn = document.getElementById("langToggle");
  const dropdown = document.getElementById("langDropdown");
  const options = document.querySelectorAll(".lang-option");

  if (toggleBtn && dropdown) {
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = dropdown.classList.toggle("show");
      toggleBtn.setAttribute("aria-expanded", isOpen);
    });

    options.forEach((option) => {
      option.addEventListener("click", () => {
        const lang = option.dataset.lang;
        const flagClass = option.dataset.flag;

        updateLangUI(lang, flagClass);
        dropdown.classList.remove("show");
        toggleBtn.setAttribute("aria-expanded", "false");
        applyLanguage(lang);
      });
    });

    document.addEventListener("click", (e) => {
      if (!toggleBtn.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove("show");
        toggleBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  // --- 4. Modale de confirmation (remplace window.confirm natif) ---
  const confirmOverlay = document.getElementById("confirmModalOverlay");
  const confirmMessageEl = document.getElementById("confirmModalMessage");
  const confirmBtn = document.getElementById("confirmModalConfirm");
  const cancelBtn = document.getElementById("confirmModalCancel");
  let pendingForm = null;

  function openConfirmModal(message, form) {
    pendingForm = form;
    confirmMessageEl.textContent = message;
    confirmOverlay.classList.add("show");
    confirmBtn.focus();
  }

  function closeConfirmModal() {
    pendingForm = null;
    confirmOverlay.classList.remove("show");
  }

  if (confirmOverlay) {
    document.querySelectorAll(".js-confirm-form").forEach((form) => {
      form.addEventListener("submit", (e) => {
        if (form.dataset.confirmed === "true") return;
        e.preventDefault();
        const key = form.dataset.confirmText;
        const message =
          (currentTranslations && currentTranslations[key]) ||
          form.dataset.confirmFallback ||
          "Êtes-vous sûr ?";
        openConfirmModal(message, form);
      });
    });

    confirmBtn.addEventListener("click", () => {
      if (pendingForm) {
        pendingForm.dataset.confirmed = "true";
        pendingForm.submit();
      }
      closeConfirmModal();
    });

    cancelBtn.addEventListener("click", closeConfirmModal);

    confirmOverlay.addEventListener("click", (e) => {
      if (e.target === confirmOverlay) closeConfirmModal();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && confirmOverlay.classList.contains("show")) {
        closeConfirmModal();
      }
    });
  }
});