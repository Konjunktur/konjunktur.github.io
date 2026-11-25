(() => {
  let dialog;
  let lastTrigger;

  function createDialog() {
    const element = document.createElement("dialog");
    element.className = "dashboard-table-modal";
    element.setAttribute("aria-labelledby", "dashboard-table-modal-title");

    const header = document.createElement("div");
    header.className = "dashboard-table-modal__header";

    const title = document.createElement("h2");
    title.id = "dashboard-table-modal-title";
    title.className = "dashboard-table-modal__title";

    const close = document.createElement("button");
    close.className = "dashboard-table-modal__close";
    close.type = "button";
    close.setAttribute("aria-label", document.documentElement.lang.startsWith("en") ? "Close" : "Schließen");
    close.textContent = "×";
    close.addEventListener("click", () => element.close());

    const content = document.createElement("div");
    content.className = "dashboard-table-modal__content";

    header.append(title, close);
    element.append(header, content);
    element.addEventListener("click", (event) => {
      if (event.target === element) element.close();
    });
    element.addEventListener("close", () => {
      content.replaceChildren();
      lastTrigger?.focus();
    });
    document.body.append(element);
    return element;
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target instanceof Element
      ? event.target.closest("[data-table-modal]")
      : null;
    if (!trigger) return;

    const table = document.getElementById(trigger.dataset.tableModal);
    if (!table) {
      console.error(`Fullscreen table not found: ${trigger.dataset.tableModal}`);
      return;
    }

    event.preventDefault();
    dialog ??= createDialog();
    lastTrigger = trigger;
    dialog.querySelector(".dashboard-table-modal__title").textContent = trigger.textContent.trim();
    const tableCopy = table.cloneNode(true);
    tableCopy.removeAttribute("id");
    dialog.querySelector(".dashboard-table-modal__content").replaceChildren(tableCopy);
    dialog.showModal();
    dialog.querySelector(".dashboard-table-modal__close").focus();
  });
})();
