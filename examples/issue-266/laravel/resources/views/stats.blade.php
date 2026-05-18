<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Visitor stats</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f3f5f7;
            color: #1f2937;
        }

        header,
        main {
            width: min(1120px, calc(100vw - 32px));
            margin: 0 auto;
        }

        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 24px 0;
        }

        main {
            display: grid;
            grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
            gap: 24px;
            padding-bottom: 32px;
        }

        section {
            padding: 20px;
            background: #ffffff;
            border: 1px solid #d8dee4;
            border-radius: 8px;
        }

        canvas {
            width: 100%;
            min-height: 320px;
        }

        button {
            min-height: 36px;
            padding: 0 16px;
            border: 0;
            border-radius: 6px;
            background: #1f2937;
            color: #ffffff;
            cursor: pointer;
        }

        @media (max-width: 800px) {
            main {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <header>
        <h1>Статистика посещений</h1>
        <form method="post" action="/stats/logout">
            @csrf
            <button type="submit">Выйти</button>
        </form>
    </header>
    <main>
        <section>
            <h2>Уникальные посещения по часам</h2>
            <canvas id="hourlyChart"></canvas>
        </section>
        <section>
            <h2>Города</h2>
            <canvas id="cityChart"></canvas>
        </section>
    </main>
    <script>
        const hourlyLabels = @json($hourly->pluck('hour'));
        const hourlyValues = @json($hourly->pluck('visits'));
        const cityLabels = @json($cities->pluck('city'));
        const cityValues = @json($cities->pluck('visits'));

        new Chart(document.getElementById("hourlyChart"), {
            type: "bar",
            data: {
                labels: hourlyLabels,
                datasets: [{
                    label: "Уникальные посещения",
                    data: hourlyValues,
                    backgroundColor: "#2563eb"
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });

        new Chart(document.getElementById("cityChart"), {
            type: "pie",
            data: {
                labels: cityLabels,
                datasets: [{
                    data: cityValues,
                    backgroundColor: ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"]
                }]
            },
            options: {
                responsive: true
            }
        });
    </script>
</body>
</html>
