import http from 'k6/http';

// Demo ramp: 5 req/s -> 30 req/s over 2 min, held for 1 min, then down.
// 30 req/s exceeds the capacity of 1 pod (C = 18 req/s), so it forces a scale-up.
export const options = {
  scenarios: {
    ramp_demo: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 300,
      stages: [
        { target: 5, duration: '30s' },
        { target: 30, duration: '2m' },
        { target: 30, duration: '1m' },
        { target: 5, duration: '30s' },
      ],
    },
  },
};

export default function () {
  http.get('http://catalog-service:3003/api/books');
}
