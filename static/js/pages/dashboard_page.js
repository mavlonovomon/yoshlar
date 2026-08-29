(function () {
    "use strict";

    const PALETTE = ["#4f46e5", "#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

    function toChartData(items) {
        return {
            labels: (items || []).map(function (item) { return item.label; }),
            values: (items || []).map(function (item) { return Number(item.count) || 0; }),
        };
    }

    function renderDoughnut(canvasId, items, tooltipSuffix) {
        const chartData = toChartData(items);
        if (!chartData.labels.length) return;
        window.dashboardCharts.createDoughnutChart(
            canvasId,
            chartData.labels,
            chartData.values,
            PALETTE.slice(0, chartData.labels.length),
            {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "58%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 12, padding: 12 },
                    },
                    tooltip: {
                        backgroundColor: "#1a1a2e",
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function (context) {
                                const total = context.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                                const percent = total ? Math.round((context.parsed / total) * 100) : 0;
                                return context.parsed + " " + tooltipSuffix + " (" + percent + "%)";
                            },
                        },
                    },
                },
            }
        );
    }

    function renderBar(canvasId, items, options) {
        const chartData = toChartData(items);
        if (!chartData.labels.length) return;
        const horizontal = options && options.horizontal;

        window.dashboardCharts.createChart(canvasId, {
            type: "bar",
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: (options && options.datasetLabel) || "Son",
                    data: chartData.values,
                    backgroundColor: (options && options.color) || "#4f46e5",
                    borderRadius: 6,
                }],
            },
            options: {
                indexAxis: horizontal ? "y" : "x",
                responsive: true,
                maintainAspectRatio: false,
                scales: horizontal
                    ? {
                        x: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            grid: { color: "rgba(0, 0, 0, 0.06)" },
                        },
                        y: { grid: { display: false } },
                    }
                    : {
                        x: {
                            grid: { display: false },
                            ticks: {
                                maxRotation: 20,
                                autoSkip: false,
                                callback: function (value) {
                                    const label = this.getLabelForValue(value);
                                    return label.length > 14 ? label.slice(0, 13) + "…" : label;
                                },
                            },
                        },
                        y: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            grid: { color: "rgba(0, 0, 0, 0.06)" },
                        },
                    },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "#1a1a2e",
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            title: function (items) {
                                return items[0].label;
                            },
                            label: function (context) {
                                const value = horizontal ? context.parsed.x : context.parsed.y;
                                return value + " " + ((options && options.tooltipSuffix) || "");
                            },
                        },
                    },
                },
            },
        });
    }

    function hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
    }

    function renderMultiLine(canvasId, items) {
        if (!items || !items.length) return;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        const labels = items.map(function(item) { return item.age + " yosh"; });
        const erkaklarData = items.map(function(item) { return Number(item.erkaklar) || 0; });
        const ayollarData = items.map(function(item) { return Number(item.ayollar) || 0; });

        const erkaklarColor = "#3b82f6";
        const ayollarColor = "#ef4444";

        window.dashboardCharts.createChart(canvasId, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Erkaklar",
                        data: erkaklarData,
                        borderColor: erkaklarColor,
                        backgroundColor: hexToRgba(erkaklarColor, 0.1),
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: "#ffffff",
                        pointBorderColor: erkaklarColor,
                        pointBorderWidth: 2,
                    },
                    {
                        label: "Ayollar",
                        data: ayollarData,
                        borderColor: ayollarColor,
                        backgroundColor: hexToRgba(ayollarColor, 0.1),
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: "#ffffff",
                        pointBorderColor: ayollarColor,
                        pointBorderWidth: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxRotation: 0, autoSkipPadding: 10 },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0 },
                        grid: { color: "rgba(0, 0, 0, 0.06)" },
                    },
                },
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 12, padding: 16 },
                    },
                    tooltip: {
                        backgroundColor: "#1a1a2e",
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            title: function(items) {
                                return items[0].label;
                            },
                            label: function(context) {
                                return context.dataset.label + ": " + context.parsed.y + " ta";
                            },
                        },
                    },
                },
            },
        });
    }

    function renderTimeline(canvasId, items, options) {
        const chartData = toChartData(items);
        if (!chartData.labels.length) return;

        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        const ctx2d = ctx.getContext("2d");
        const color = (options && options.color) || "#4f46e5";
        const gradient = ctx2d.createLinearGradient(0, 0, 0, 320);
        gradient.addColorStop(0, hexToRgba(color, 0.35));
        gradient.addColorStop(1, hexToRgba(color, 0.02));

        window.dashboardCharts.createChart(canvasId, {
            type: "line",
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: (options && options.datasetLabel) || "Tadbirlar",
                    data: chartData.values,
                    borderColor: color,
                    backgroundColor: gradient,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointBackgroundColor: "#ffffff",
                    pointBorderColor: color,
                    pointBorderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxRotation: 0, autoSkipPadding: 20 },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0 },
                        grid: { color: "rgba(0, 0, 0, 0.06)" },
                    },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "#1a1a2e",
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function (context) {
                                return context.parsed.y + " " + ((options && options.tooltipSuffix) || "ta tadbir");
                            },
                        },
                    },
                },
            },
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!window.dashboardCharts || typeof Chart === "undefined") {
            return;
        }

        const charts = window.dashboardCharts.parseJsonScript("module-charts-data") || {};

        // Timeline chart
        const timeline = window.dashboardCharts.parseJsonScript("meeting-timeline-data") || [];
        const ctx = document.getElementById("meetingTimelineChart");
        if (ctx && timeline.length) {
            const gradient = ctx.getContext("2d").createLinearGradient(0, 0, 0, 320);
            gradient.addColorStop(0, "rgba(79, 70, 229, 0.35)");
            gradient.addColorStop(1, "rgba(79, 70, 229, 0.02)");

            window.dashboardCharts.createChart("meetingTimelineChart", {
                type: "line",
                data: {
                    labels: timeline.map(function (item) { return item.label; }),
                    datasets: [{
                        label: "Suhbatlar soni",
                        data: timeline.map(function (item) { return Number(item.count) || 0; }),
                        borderColor: "#4f46e5",
                        backgroundColor: gradient,
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: "#ffffff",
                        pointBorderColor: "#4f46e5",
                        pointBorderWidth: 2,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { maxRotation: 0, autoSkipPadding: 20 },
                        },
                        y: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            grid: { color: "rgba(0, 0, 0, 0.06)" },
                        },
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: "#1a1a2e",
                            padding: 12,
                            cornerRadius: 8,
                            callbacks: {
                                label: function (context) {
                                    return context.parsed.y + " ta suhbat";
                                },
                            },
                        },
                    },
                },
            });
        }

        // Age-gender distribution chart
        const ageGender = window.dashboardCharts.parseJsonScript("age-gender-data") || [];
        renderMultiLine("ageGenderChart", ageGender);

        const unemployed = charts.unemployed || {};
        renderDoughnut("unemployedCategoryChart", unemployed.categories, "ta");
        renderBar("assistanceTypeChart", unemployed.assistance_types, {
            horizontal: true,
            color: "#0ea5e9",
            datasetLabel: "Yordam ko'rsatilgan",
            tooltipSuffix: "ta yoshga",
        });

        const otaliq = charts.otaliq || {};
        renderDoughnut("otaliqCategoryChart", otaliq.categories, "ta");
        renderBar("otaliqAssistanceChart", otaliq.assistance_types, {
            horizontal: true,
            color: "#0ea5e9",
            datasetLabel: "Yordam ko'rsatilgan",
            tooltipSuffix: "ta yoshga",
        });

        const migratsiya = charts.migratsiya || {};
        renderBar("migratsiyaReasonChart", migratsiya.reasons, {
            color: "#f59e0b",
            tooltipSuffix: "ta yosh",
        });
        renderBar("migratsiyaCountryChart", migratsiya.top_countries, {
            color: "#8b5cf6",
            datasetLabel: "Yoshlar",
            tooltipSuffix: "ta yosh",
        });

        const reyd = charts.reyd || {};
        renderDoughnut("reydTypeChart", reyd.types, "ta tadbir");
        renderTimeline("reydTimelineChart", reyd.timeline, {
            color: "#ef4444",
            datasetLabel: "Reyd tadbirlari",
            tooltipSuffix: "ta reyd",
        });

        const besh = charts.besh || {};
        renderBar("beshDirectionChart", besh.directions, {
            color: "#22c55e",
            datasetLabel: "Qamrov",
            tooltipSuffix: "kishiga",
        });
        renderTimeline("beshTimelineChart", besh.timeline, {
            color: "#14b8a6",
            datasetLabel: "Besh tashabbus",
            tooltipSuffix: "ta tadbir",
        });
    });
})();
