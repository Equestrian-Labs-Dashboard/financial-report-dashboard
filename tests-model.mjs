import fs from 'node:fs'; import vm from 'node:vm'; import assert from 'node:assert/strict';
const assumptions=JSON.parse(fs.readFileSync(new URL('./data/assumptions.json',import.meta.url),'utf8'));
const source=fs.readFileSync(new URL('./assets/js/app.js',import.meta.url),'utf8');
const test=`STATE=${JSON.stringify(assumptions)}; const R={};
STATE.operations.find(r=>r.driver==='Outbound Shipping Cost %').y2026='10%'; STATE.operations.find(r=>r.driver==='Packaging Cost %').y2026='5%'; STATE.operations.find(r=>r.driver==='Shipping Revenue %').y2026='2%';
let b=marginBridge('y2026'); assert.ok(Math.abs(b.gp2-(b.gp1-b.netSales*.10-b.netSales*.05+b.netSales*.02))<.01); assert.ok(Math.abs(b.gp3-(b.gp2-b.adSpend))<.01); R.gp={gp1:b.gp1,gp2:b.gp2,gp3:b.gp3};
STATE.meta.fundingScenario='$3M'; STATE.meta.fundingDate='Jan-27'; assert.equal(cashFlowRows('y2026').cashIn.Funding,0); assert.equal(cashFlowRows('y2027').cashIn.Funding,3000000);
assert.deepEqual(embroideryLaunchStart(),{year:2027,month:3}); assert.deepEqual(privateLabelLaunchStart(),{year:2028,month:3}); assert.equal(launchFactorForEngine('Embroidery','y2027'),.75); assert.equal(launchFactorForEngine('Private Label','y2028'),.75);
let d1=doverRampPct('y2026'),p1=ecommerceBuild('y2026').paid; STATE.meta.fundingDate='Oct-26'; let d2=doverRampPct('y2026'),p2=ecommerceBuild('y2026').paid; assert.ok(d2>d1); assert.ok(p2>p1); assert.deepEqual(privateLabelLaunchStart(),{year:2028,month:0});
// Dover selector is the source of truth and must refresh the full dependent
// build, including its 2026 5% ramp and 30% paid-media overlap.
for (const [capture, expected] of [['15%',682500],['10%',455000],['5%',227500]]) { STATE.meta.doverCapture=capture; syncHeaderToTables(); assert.ok(Math.abs(netDoverCapture('y2026')-expected)<0.01); }
// $3M arriving in October should have a limited Q4 2026 uplift, but more
// funding-backed paid capacity in 2027 than the $1M case.
STATE.meta.doverCapture='20%'; STATE.meta.fundingScenario='$1M'; STATE.meta.fundingDate='Oct-26'; const oneM26=ecommerceBuild('y2026').paid, oneM27=ecommerceBuild('y2027').paid;
STATE.meta.fundingScenario='$3M'; const threeM26=ecommerceBuild('y2026').paid, threeM27=ecommerceBuild('y2027').paid;
assert.ok(threeM26 > oneM26); assert.ok(threeM26 - oneM26 < 200000); assert.ok(threeM27 > oneM27);
// Inventory is a cash investment, never a GM1 input.  The agreed GM1 path is
// gradual and remains unchanged even when the $3M inventory allocation moves.
const ecommerce=getBlock(STATE.growthEngines,'Ecommerce'); assert.deepEqual(['y2027','y2028','y2029'].map(y=>val(ecommerce.rows,'GM1 %',y)),['37%','42%','46%']);
const gmBefore=marginBridge('y2027').gp1 / marginBridge('y2027').netSales; selectedFundingRow().inventory=0; const gmAfter=marginBridge('y2027').gp1 / marginBridge('y2027').netSales; assert.equal(gmAfter,gmBefore);
assert.equal(STATE.meta.shopifyOrderAudit.value,3616); R.funding={jan27:{dover:d1,paid:p1},oct26:{dover:d2,paid:p2},cash2027:3000000,oneM26,oneM27,threeM26,threeM27}; globalThis.__R=R;`;
const sandbox={console,assert,document:{addEventListener(){},createElement(){return{setAttribute(){},appendChild(){},addEventListener(){},style:{}}},createTextNode(v){return v},getElementById(){return null},body:{setAttribute(){},getAttribute(){return'light'}}},localStorage:{getItem(){return null},setItem(){}},DataService:{},window:{},location:{reload(){}},alert(){},confirm(){return false},setTimeout,clearTimeout,Date,Math,Number,String,Object,Array,JSON,Map,Set}; vm.createContext(sandbox); vm.runInContext(source+'\n'+test,sandbox); console.log(JSON.stringify(sandbox.__R,null,2));
