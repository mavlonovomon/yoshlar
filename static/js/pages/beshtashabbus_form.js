(function () {
    "use strict";

    function refillTitles(directionSelect, titleSelect, titleOptionsByDirection) {
        if (!directionSelect || !titleSelect) return;

        var selectedDirection = directionSelect.value;
        var previousValue = titleSelect.value;
        var options = titleOptionsByDirection[selectedDirection] || [];

        titleSelect.innerHTML = "";

        var placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Tadbir nomini tanlang";
        titleSelect.appendChild(placeholder);

        options.forEach(function (name) {
            var option = document.createElement("option");
            option.value = name;
            option.textContent = name;
            if (name === previousValue) {
                option.selected = true;
            }
            titleSelect.appendChild(option);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var directionSelect = document.getElementById("id_direction");
        var titleSelect = document.getElementById("id_title");
        var titleOptionsNode = document.getElementById("besh-title-options");
        if (!directionSelect || !titleSelect || !titleOptionsNode) {
            return;
        }

        var titleOptionsByDirection = {};
        try {
            titleOptionsByDirection = JSON.parse(titleOptionsNode.textContent);
        } catch (_err) {
            titleOptionsByDirection = {};
        }

        directionSelect.addEventListener("change", function () {
            titleSelect.value = "";
            refillTitles(directionSelect, titleSelect, titleOptionsByDirection);
        });

        refillTitles(directionSelect, titleSelect, titleOptionsByDirection);
    });
})();
