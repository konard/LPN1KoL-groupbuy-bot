import { createStore } from 'vuex';

export default createStore({
  state: {
    feedbackItems: [],
  },
  mutations: {
    addFeedback(state, feedback) {
      state.feedbackItems.push(feedback);
    },
  },
});
