(function () {
  function init() {
    const typeField = document.querySelector('select[name="type_val"]');

    if (!typeField) {
      return;
    }

    const fields = Array.from(document.querySelectorAll("input[name], select[name], textarea[name], button[name]"));

    function getContainer(field) {
      return field.closest("p, label, div, li, tr, fieldset") || field;
    }

    function updateVisibility() {
      const value = String(typeField.value);

      fields.forEach(function (field) {
        if (field === typeField) {
          getContainer(field).style.display = "";
          return;
        }

        const name = field.getAttribute("name") || "";
        getContainer(field).style.display = name.includes(value) ? "" : "none";
      });
    }

    typeField.addEventListener("change", updateVisibility);
    updateVisibility();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
