<template>
  <section>
    <h1>Feedback</h1>
    <form @submit.prevent="submit">
      <label>
        Name
        <input v-model="form.name" name="name" required type="text" />
      </label>
      <label>
        Message
        <textarea v-model="form.message" name="message" required />
      </label>
      <button type="submit">Send</button>
    </form>
  </section>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      form: {
        name: '',
        message: '',
      },
    };
  },
  methods: {
    async submit() {
      const feedback = { ...this.form };

      await axios.post('/api/feedback', feedback);
      this.$store.commit('addFeedback', feedback);

      this.form.name = '';
      this.form.message = '';
      this.$router.push('/feedback');
    },
  },
};
</script>
