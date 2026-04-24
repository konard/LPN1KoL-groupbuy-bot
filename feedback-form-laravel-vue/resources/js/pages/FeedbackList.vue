<template>
  <section>
    <h1>Submitted feedback</h1>
    <p v-if="!feedbackItems.length">No feedback submitted yet.</p>
    <ul v-else>
      <li v-for="(feedback, index) in feedbackItems" :key="index">
        <strong>{{ feedback.name }}</strong>
        <p>{{ feedback.message }}</p>
      </li>
    </ul>
  </section>
</template>

<script>
export default {
  computed: {
    feedbackItems() {
      return this.$store.state.feedbackItems;
    },
  },
};
</script>
