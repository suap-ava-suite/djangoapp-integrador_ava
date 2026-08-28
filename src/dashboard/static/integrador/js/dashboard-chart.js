(function () {
    "use strict";

    function isDarkMode() {
        if (document.documentElement.dataset.theme === "dark") {
            return true;
        }
        if (document.documentElement.dataset.theme === "light") {
            return false;
        }
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    function getChartColors() {
        const dark = isDarkMode();
        return {
            textColor: dark ? "#e0e0e0" : "#555555",
            gridColor: dark ? "rgba(255, 255, 255, 0.12)" : "rgba(0, 0, 0, 0.08)",
            datasets: [
                { label: "Total", field: "total", color: dark ? "#60a5fa" : "#417690" },
                { label: "Sucesso", field: "sucesso", color: dark ? "#4cd964" : "#28a745" },
                { label: "Falha", field: "falha", color: dark ? "#ff5b68" : "#dc3545" },
                { label: "Processando", field: "processando", color: dark ? "#ffd600" : "#d97706" },
            ],
        };
    }

    function buildDataset(label, field, color) {
        const series = window.dashboardChartData || [];
        return {
            label,
            data: series.map((point) => point[field]),
            borderColor: color,
            backgroundColor: color,
            tension: 0.25,
            pointRadius: 3,
            fill: false,
        };
    }

    function initChart() {
        const canvas = document.getElementById("solicitacoes-series-chart");
        if (!canvas) {
            return;
        }

        const series = window.dashboardChartData || [];

        if (!series || series.length === 0) {
            if (canvas.parentElement) {
                canvas.parentElement.style.display = "none";
            }
            return;
        }

        const colors = getChartColors();
        const labels = series.map((point) => point.date);
        const datasets = colors.datasets.map((cfg) => buildDataset(cfg.label, cfg.field, cfg.color));

        try {
            new Chart(canvas, {
                type: "line",
                data: { labels, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: colors.textColor },
                        },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.dataset.label}: ${ctx.formattedValue}`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: { color: colors.textColor },
                            grid: { color: colors.gridColor },
                            title: { display: true, text: "Data", color: colors.textColor },
                        },
                        y: {
                            beginAtZero: true,
                            ticks: { color: colors.textColor },
                            grid: { color: colors.gridColor },
                            title: { display: true, text: "Solicitações", color: colors.textColor },
                        },
                    },
                },
            });
        } catch (error) {
            console.error("Error initializing chart:", error);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initChart);
    } else {
        initChart();
    }
})();
