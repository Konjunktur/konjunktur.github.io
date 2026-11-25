(() => {
  let dialog;
  let lastTrigger;

  function closeMenus(except) {
    document.querySelectorAll(".dashboard-chart-menu__dropdown:not([hidden])").forEach((menu) => {
      if (menu === except) return;
      menu.hidden = true;
      menu.previousElementSibling.setAttribute("aria-expanded", "false");
    });
  }

  function getDialog() {
    if (dialog) return dialog;

    dialog = document.createElement("dialog");
    dialog.className = "dashboard-fullscreen-modal";
    dialog.setAttribute("aria-labelledby", "dashboard-fullscreen-modal-title");

    const header = document.createElement("div");
    header.className = "dashboard-fullscreen-modal__header";
    const title = document.createElement("h2");
    title.id = "dashboard-fullscreen-modal-title";
    title.className = "dashboard-fullscreen-modal__title";

    const close = document.createElement("button");
    close.className = "dashboard-fullscreen-modal__close";
    close.type = "button";
    close.setAttribute("aria-label", document.documentElement.lang.startsWith("en") ? "Close" : "Schließen");
    close.textContent = "×";
    close.addEventListener("click", () => dialog.close());

    const content = document.createElement("div");
    content.className = "dashboard-fullscreen-modal__content";
    header.append(title, close);
    dialog.append(header, content);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", () => {
      content.replaceChildren();
      lastTrigger?.focus();
    });
    document.body.append(dialog);
    return dialog;
  }

  function showModal(titleText, contentElement, trigger) {
    const modal = getDialog();
    lastTrigger = trigger;
    modal.querySelector(".dashboard-fullscreen-modal__title").textContent = titleText;
    modal.querySelector(".dashboard-fullscreen-modal__content").replaceChildren(contentElement);
    modal.showModal();
    modal.querySelector(".dashboard-fullscreen-modal__close").focus();
  }

  function showTable(trigger) {
    const table = document.getElementById(trigger.dataset.tableModal);
    if (!table) {
      console.error(`Fullscreen table not found: ${trigger.dataset.tableModal}`);
      return;
    }
    const copy = table.cloneNode(true);
    copy.removeAttribute("id");
    showModal(trigger.textContent.trim(), copy, trigger);
  }

  function showChart(trigger) {
    const frame = document.createElement("iframe");
    frame.className = "dashboard-fullscreen-modal__chart";
    frame.src = trigger.dataset.chartModal;
    frame.title = trigger.textContent.trim();
    showModal(trigger.textContent.trim(), frame, trigger);
  }

  function printChart(trigger) {
    const printWindow = window.open(trigger.dataset.chartPrint, "_blank");
    if (!printWindow) {
      console.error("The chart print window was blocked by the browser.");
      return;
    }
    printWindow.addEventListener("load", () => {
      printWindow.focus();
      printWindow.print();
    }, { once: true });
  }

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const toggle = event.target.closest(".dashboard-chart-menu__toggle");
    if (toggle) {
      const menu = document.getElementById(toggle.getAttribute("aria-controls"));
      if (!menu) {
        console.error(`Chart menu not found: ${toggle.getAttribute("aria-controls")}`);
        return;
      }
      const shouldOpen = menu.hidden;
      closeMenus(menu);
      menu.hidden = !shouldOpen;
      toggle.setAttribute("aria-expanded", String(shouldOpen));
      return;
    }

    const chartAction = event.target.closest("[data-chart-modal]");
    const tableAction = event.target.closest("[data-table-modal]");
    const printAction = event.target.closest("[data-chart-print]");
    const downloadAction = event.target.closest(".dashboard-chart-menu__dropdown a[download]");
    if (chartAction || tableAction || printAction) {
      closeMenus();
      if (chartAction) showChart(chartAction);
      else if (tableAction) showTable(tableAction);
      else printChart(printAction);
      return;
    }
    if (downloadAction) {
      closeMenus();
      return;
    }

    if (!event.target.closest(".dashboard-chart-menu__dropdown")) closeMenus();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const openMenu = document.querySelector(".dashboard-chart-menu__dropdown:not([hidden])");
    if (!openMenu) return;
    openMenu.hidden = true;
    openMenu.previousElementSibling.setAttribute("aria-expanded", "false");
  });
})();
