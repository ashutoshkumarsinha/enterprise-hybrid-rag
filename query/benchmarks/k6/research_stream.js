/**
 * k6 load test — POST /research/stream (SSE)
 * Platform §13.1, TL-09
 *
 * Usage:
 *   k6 run -e QUERY_URL=http://localhost:8010 benchmarks/k6/research_stream.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

const QUERY_URL = __ENV.QUERY_URL || 'http://localhost:8010';
const TENANT_ID = __ENV.TENANT_ID || 'acme-corp';
const COLLECTION_ID = __ENV.COLLECTION_ID || 'payments-api';

export const options = {
  scenarios: {
    scoped_faq: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 50),
      duration: __ENV.DURATION || '30m',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.001'],
    http_req_duration: ['p(95)<20000'],
  },
};

const PAYLOAD = JSON.stringify({
  query: 'What is the API rate limit?',
  tenant_id: TENANT_ID,
  collection_id: COLLECTION_ID,
});

export default function () {
  const res = http.post(`${QUERY_URL}/research/stream`, PAYLOAD, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '120s',
  });
  check(res, {
    'status is 200': (r) => r.status === 200,
    'body mentions telemetry or token': (r) =>
      r.body && (r.body.includes('telemetry') || r.body.includes('token') || r.body.includes('done')),
  });
  sleep(1);
}
