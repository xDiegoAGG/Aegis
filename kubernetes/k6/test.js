import http from 'k6/http';

export const options = {
  scenarios: {
    step_5: { executor: 'constant-arrival-rate', rate: 5, timeUnit: '1s', duration: '1m', preAllocatedVUs: 50, startTime: '0s' },
    step_10: { executor: 'constant-arrival-rate', rate: 10, timeUnit: '1s', duration: '1m', preAllocatedVUs: 50, startTime: '1m' },
    step_14: { executor: 'constant-arrival-rate', rate: 14, timeUnit: '1s', duration: '1m', preAllocatedVUs: 50, startTime: '2m' },
  },
};

export default function () {
  http.get('http://catalog-service:3003/api/books');
}
