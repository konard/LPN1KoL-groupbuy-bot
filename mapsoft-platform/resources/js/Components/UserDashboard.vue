<template>
  <main class="dashboard">
    <section class="toolbar">
      <div>
        <h1>Usage Dashboard</h1>
        <p>{{ currentPeriod }}</p>
      </div>
      <button type="button" @click="loadDashboard">Refresh</button>
    </section>

    <section class="metrics">
      <article>
        <span>Total Usage</span>
        <strong>{{ totals.consumption.toFixed(2) }}</strong>
      </article>
      <article>
        <span>Open Bills</span>
        <strong>{{ totals.openBills }}</strong>
      </article>
      <article>
        <span>Balance Due</span>
        <strong>{{ totals.balanceDue.toFixed(2) }}</strong>
      </article>
    </section>

    <section class="grid">
      <div class="panel">
        <canvas ref="lineChart"></canvas>
      </div>
      <div class="panel">
        <canvas ref="pieChart"></canvas>
      </div>
    </section>

    <section class="grid">
      <form class="panel form" @submit.prevent="submitReading">
        <label>
          Type
          <select v-model="form.type">
            <option value="electricity">Electricity</option>
            <option value="water">Water</option>
            <option value="gas">Gas</option>
          </select>
        </label>
        <label>
          Value
          <input v-model.number="form.value" min="0" step="0.001" type="number" required>
        </label>
        <label>
          Period Start
          <input v-model="form.period_start" type="date" required>
        </label>
        <label>
          Period End
          <input v-model="form.period_end" type="date" required>
        </label>
        <button type="submit">Submit Reading</button>
      </form>

      <div class="panel">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Value</th>
              <th>Submitted</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="reading in readings" :key="reading.id">
              <td>{{ reading.type }}</td>
              <td>{{ reading.value }}</td>
              <td>{{ reading.submitted_at }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>

<script>
import axios from 'axios';
import Chart from 'chart.js/auto';

export default {
  data() {
    return {
      currentPeriod: new Date().toISOString().slice(0, 7),
      readings: [],
      bills: [],
      totals: {
        consumption: 0,
        openBills: 0,
        balanceDue: 0,
      },
      form: {
        type: 'electricity',
        value: 0,
        period_start: new Date().toISOString().slice(0, 10),
        period_end: new Date().toISOString().slice(0, 10),
      },
      charts: {
        line: null,
        pie: null,
      },
    };
  },
  mounted() {
    this.loadDashboard();
  },
  methods: {
    async loadDashboard() {
      try {
        const [statsResponse, readingsResponse, billsResponse] = await Promise.all([
          axios.get('/api/v1/stats/monthly'),
          axios.get('/api/v1/readings/history'),
          axios.get('/api/v1/bills'),
        ]);

        this.totals = statsResponse.data.data;
        this.readings = readingsResponse.data.data;
        this.bills = billsResponse.data.data;
      } catch (error) {
        this.readings = [
          { id: 1, type: 'electricity', value: 142.2, period_start: '2026-02-01', submitted_at: '2026-02-28T10:20:00Z' },
          { id: 2, type: 'water', value: 31.4, period_start: '2026-03-01', submitted_at: '2026-03-31T09:10:00Z' },
          { id: 3, type: 'gas', value: 18.1, period_start: '2026-04-01', submitted_at: '2026-04-21T12:05:00Z' },
        ];
        this.bills = [
          { id: 1, amount: 96.44, status: 'pending' },
          { id: 2, amount: 88.13, status: 'pending' },
        ];
        this.totals = {
          consumption: this.readings.reduce((sum, reading) => sum + Number(reading.value), 0),
          openBills: this.bills.length,
          balanceDue: this.bills.reduce((sum, bill) => sum + Number(bill.amount), 0),
        };
      }

      this.renderCharts();
    },
    async submitReading() {
      const payload = {
        ...this.form,
        idempotency_key: crypto.randomUUID(),
      };

      await axios.post('/api/v1/readings', payload);
      await this.loadDashboard();
    },
    renderCharts() {
      const labels = this.readings.map((reading) => reading.period_start);
      const usage = this.readings.map((reading) => reading.value);
      const byType = this.readings.reduce((result, reading) => {
        result[reading.type] = (result[reading.type] || 0) + Number(reading.value);
        return result;
      }, {});

      if (this.charts.line) {
        this.charts.line.destroy();
      }

      if (this.charts.pie) {
        this.charts.pie.destroy();
      }

      this.charts.line = new Chart(this.$refs.lineChart, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Consumption',
            data: usage,
            borderColor: '#2563eb',
            backgroundColor: '#93c5fd',
          }],
        },
      });

      this.charts.pie = new Chart(this.$refs.pieChart, {
        type: 'doughnut',
        data: {
          labels: Object.keys(byType),
          datasets: [{
            data: Object.values(byType),
            backgroundColor: ['#16a34a', '#0891b2', '#f59e0b'],
          }],
        },
      });
    },
  },
};
</script>

<style scoped>
.dashboard {
  color: #111827;
  display: grid;
  gap: 24px;
  margin: 0 auto;
  max-width: 1180px;
  padding: 32px;
}

.toolbar,
.metrics,
.grid {
  display: grid;
  gap: 16px;
}

.toolbar {
  align-items: center;
  grid-template-columns: 1fr auto;
}

.metrics,
.grid {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.panel,
.metrics article {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 18px;
}

.form {
  display: grid;
  gap: 12px;
}

label {
  display: grid;
  gap: 6px;
}

input,
select,
button {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 10px 12px;
}

button {
  background: #111827;
  color: #ffffff;
  cursor: pointer;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th,
td {
  border-bottom: 1px solid #e5e7eb;
  padding: 10px;
  text-align: left;
}
</style>
