(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const cells = document.querySelectorAll(".status-cell");
        if (!cells.length) {
            return;
        }

        cells.forEach(function (cell) {
            const value = parseFloat(cell.dataset.percent || "");
            if (Number.isNaN(value)) {
                return;
            }

            cell.classList.remove("status-zero", "status-low", "status-medium", "status-high");

            if (value <= 0) {
                cell.classList.add("status-zero");
            } else if (value < 25) {
                cell.classList.add("status-low");
            } else if (value < 50) {
                cell.classList.add("status-medium");
            } else {
                cell.classList.add("status-high");
            }
        });
    });
})();
