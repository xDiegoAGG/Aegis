import http from 'k6/http';

// Demo ramp: 5 req/s -> 50 req/s over 2 min, held for 1 min, then down.
// 50 req/s exceeds the capacity of 1 pod (calibrated C = 32 req/s, test 14) but not of 2 pods.
// Until test 15 the peak was 30 req/s, chosen when C was 18 (keep-alive traffic).
export const options = {
  // One new connection per request. A Kubernetes Service picks a pod per connection,
  // so with keep-alive the traffic stayed on the old pod after a scale-up (test 11).
  noConnectionReuse: true,
  scenarios: {
    ramp_demo: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 400,
      stages: [
        { target: 5, duration: '30s' },
        { target: 50, duration: '2m' },
        { target: 50, duration: '1m' },
        { target: 5, duration: '30s' },
      ],
    },
  },
};

export default function () {
  // Client-side timeout: a request waiting longer than this counts as failed
  http.get('http://catalog-service:3003/api/books', { timeout: '10s' });
}
