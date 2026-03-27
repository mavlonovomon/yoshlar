(function () {
    "use strict";

    function loadNumber(id) {
        const parsed = window.dashboardCharts.parseJsonScript(id);
        const value = Number(parsed);
        return Number.isFinite(value) ? value : 0;
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!window.dashboardCharts || typeof Chart === "undefined") {
            return;
        }

        const covered = loadNumber("meeting-covered-count");
        const pending = loadNumber("meeting-pending-count");
        const moduleSummary = window.dashboardCharts.parseJsonScript("module-summary-data") || [];

        window.dashboardCharts.createDoughnutChart(
            "meetingStatusChart",
            ["Suhbat o'tkazilgan", "Kutilmoqda"],
            [covered, pending],
            ["#22c55e", "#ef4444"],
            {
                plugins: {
                    legend: {
                        position: "bottom",
                    },
                },
                cutout: "68%",
                responsive: true,
                maintainAspectRatio: false,
            }
        );

        const labels = moduleSummary.map(function (item) {
            return item.title;
        });
        const values = moduleSummary.map(function (item) {
            return Number(item.value) || 0;
        });

        window.dashboardCharts.createBarChart(
            "moduleSummaryChart",
            labels,
            values,
            "Yozuvlar soni",
            {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0,
                        },
                    },
                },
                plugins: {
                    legend: {
                        display: false,
                    },
                },
            },
            "#4f46e5"
        );
    });
})();
