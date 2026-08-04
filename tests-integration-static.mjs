import fs from 'node:fs';
import assert from 'node:assert/strict';

const app = fs.readFileSync('assets/js/app.js','utf8');
const sync = fs.readFileSync('scripts/sync-shopify-actuals.mjs','utf8');
const workflow = fs.readFileSync('.github/workflows/deploy.yml','utf8');
const assumptions = JSON.parse(fs.readFileSync('data/assumptions.json','utf8'));

assert.match(sync, /inventoryItem\s*\{\s*unitCost/s, 'Shopify sync must request variant unit cost');
assert.match(sync, /agg\.cogs \+= cogs/, 'Shopify sync must aggregate COGS');
assert.match(sync, /agg\.gross_profit \+= net - cogs/, 'Shopify sync must aggregate GP');
assert.match(sync, /gross_margin:/, 'Channel revenue share must expose gross margin');
assert.match(app, /ecommerceMetrics\.gm1 \|\| corro\.gm1/, 'Ecommerce current GM1 must prefer ecommerce channel GM1');
assert.equal((app.match(/setCavaliForecastFields\(cavaliEngine, cavali, cavaliAds\)/g) || []).length, 1, 'Refresh must not invoke Cavali forecast overwrite');
assert.match(app, /saveScenarioInputs\(STATE\.meta\.modelStatus \|\| "Draft"\)/, 'Save must snapshot active scenario');
assert.match(app, /DataService\.save\(STATE\)/, 'Save must persist complete model state');
assert.match(app, /scheduleSave\(\)/, 'Editable changes must schedule persistence');
assert.match(workflow, /GOOGLE_CREDENTIALS/, 'Workflow must use Google service credentials');
assert.match(workflow, /SHEET_ID_CORRO/, 'Workflow must use Corro sheet');
assert.match(workflow, /SHEET_ID_CAVALI/, 'Workflow must use Cavali sheet');
assert.match(workflow, /ADS_SHEET_ID/, 'Workflow must use Stats sheet');

for (const name of ['Ecommerce','Concierge','Wellington','Cavali']) {
  const block = assumptions.growthEngines.find(b => b.title.startsWith(name));
  assert.ok(block, `${name} block missing`);
  const gm = block.rows.find(r => r.driver === 'GM1 %');
  assert.ok(gm, `${name} GM1 row missing`);
}

console.log('PASS: persistence, scenario save, channel GM1, Shopify unit-cost COGS, workflow credentials');

assert.match(app, /Checkout Abandonment Rate/, 'Financial Summary must include Checkout Abandonment Rate');
assert.match(app, /filter\(name => name !== "Operating Cash Out"\)/, 'Cash Out detail must not visually duplicate Operating Cash Out subtotal');
assert.match(app, /versionBadge"\)\.textContent = "v2\.1"/, 'Visible model version must be v2.1');
const cavali = assumptions.growthEngines.find(b => b.title.startsWith('Cavali'));
assert.equal(cavali.rows.find(r=>r.driver==='Cavali CAC').y2026, '—', 'Cavali CAC must not default to a fake $100');
assert.equal(cavali.rows.find(r=>r.driver==='Cavali Ad Spend').y2026, '—', 'Cavali Ad Spend must not default to fake zero');
assert.equal(assumptions.growthInitiatives.find(x=>x.initiative==='Market Expansion').launch, 'TBD', 'Market Expansion timing must remain unconfirmed');
