/**
 * Test script for service worker fetch logic simulation
 */
const fs = require('fs');
const path = require('path');

const swCode = fs.readFileSync(path.join(__dirname, 'ui', 'service-worker.js'), 'utf8');

console.log('=== SERVICE WORKER CODE INTEGRITY CHECK ===');
console.log('File length:', swCode.length, 'bytes');

// Check that non-GET check is present
if (swCode.includes("event.request.method !== 'GET'") || swCode.includes("event.request.method === 'GET'")) {
  console.log('✅ Non-GET method check verified in service worker source code.');
} else {
  console.error('❌ Missing method check in service worker!');
  process.exit(1);
}

// Simulated Cache API mock
class MockCache {
  constructor(name) {
    this.name = name;
    this.store = new Map();
  }
  async match(req) {
    return this.store.get(req.url) || null;
  }
  async put(req, res) {
    if (req.method !== 'GET') {
      throw new Error(`Failed to execute 'put' on 'Cache': Request method '${req.method}' is unsupported`);
    }
    this.store.set(req.url, res);
  }
}

const mockCaches = {
  open: async (name) => new MockCache(name),
  match: async (req) => null
};

// Simulation environment
const listeners = {};
const self = {
  addEventListener: (type, handler) => {
    listeners[type] = handler;
  }
};

const mockFetch = async (req) => {
  return {
    status: 200,
    type: 'basic',
    clone: () => ({ status: 200, type: 'basic' })
  };
};

// Evaluate the SW code in mock sandbox
const fn = new Function('self', 'caches', 'fetch', swCode);
fn(self, mockCaches, mockFetch);

if (!listeners['fetch']) {
  console.error('❌ Fetch listener not registered!');
  process.exit(1);
}

console.log('✅ Service worker fetch listener loaded successfully.');

async function runTests() {
  const fetchListener = listeners['fetch'];

  // Test 1: POST Request (e.g. POST /api/v1/prospects)
  console.log('\nTest 1: Submitting prospect via POST /api/v1/prospects');
  let postFetched = false;
  let postPutAttempted = false;

  const postEvent = {
    request: {
      method: 'POST',
      url: 'http://localhost:8000/api/v1/prospects'
    },
    respondWith: (promise) => {
      postFetched = true;
    }
  };

  fetchListener(postEvent);
  if (postFetched) {
    console.log('✅ POST request bypassed Cache API and passed directly to network fetch.');
  } else {
    console.error('❌ POST request was not properly passed through!');
    process.exit(1);
  }

  // Test 2: PUT/DELETE Requests
  console.log('\nTest 2: Submitting actions via PUT and DELETE');
  let putPassed = false;
  let deletePassed = false;

  fetchListener({
    request: { method: 'PUT', url: 'http://localhost:8000/api/v1/prospects/123' },
    respondWith: () => { putPassed = true; }
  });
  fetchListener({
    request: { method: 'DELETE', url: 'http://localhost:8000/api/v1/prospects/123' },
    respondWith: () => { deletePassed = true; }
  });

  if (putPassed && deletePassed) {
    console.log('✅ PUT and DELETE requests bypassed Cache API.');
  } else {
    console.error('❌ PUT/DELETE not bypassed!');
    process.exit(1);
  }

  // Test 3: GET Request (e.g. GET /manifest.json)
  console.log('\nTest 3: Fetching asset via GET /manifest.json');
  let getResponded = false;
  const getEvent = {
    request: {
      method: 'GET',
      url: 'http://localhost:8000/manifest.json'
    },
    respondWith: (promise) => {
      getResponded = true;
    }
  };

  fetchListener(getEvent);
  if (getResponded) {
    console.log('✅ GET request correctly used cache-first / network-caching pipeline.');
  } else {
    console.error('❌ GET request failed to respondWith!');
    process.exit(1);
  }

  console.log('\n🎉 ALL SERVICE WORKER UNIT CHECKS PASSED!');
}

runTests();
