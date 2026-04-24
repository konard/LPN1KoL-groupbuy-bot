import { createRouter, createWebHistory } from 'vue-router';
import FeedbackForm from './pages/FeedbackForm.vue';
import FeedbackList from './pages/FeedbackList.vue';

const routes = [
  { path: '/', name: 'feedback-form', component: FeedbackForm },
  { path: '/feedback', name: 'feedback-list', component: FeedbackList },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
