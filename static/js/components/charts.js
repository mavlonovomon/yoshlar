(function (window) {
    function parseJsonScript(id) {
        const node = document.getElementById(id);
        if (!node) return [];
        try {
            return JSON.parse(node.textContent);
        } catch (_e) {
            return [];
        }
    }

    function createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === 'undefined') return null;
        return new Chart(canvas, config);
    }

    function createDoughnutChart(canvasId, labels, data, colors, options) {
        return createChart(canvasId, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 0,
                }],
            },
            options: options || { plugins: { legend: { position: 'bottom' } } },
        });
    }

    function createBarChart(canvasId, labels, data, datasetLabel, options, color) {
        return createChart(canvasId, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: datasetLabel,
                    data: data,
                    backgroundColor: color || '#4f46e5',
                    borderRadius: 6,
                }],
            },
            options: options || { plugins: { legend: { display: false } } },
        });
    }

    window.dashboardCharts = {
        parseJsonScript: parseJsonScript,
        createDoughnutChart: createDoughnutChart,
        createBarChart: createBarChart,
        createChart: createChart,
    };
})(window);
