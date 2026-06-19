const fs=require('fs');
const html=fs.readFileSync('Relative_PE_Dashboard.html','utf8');

// 1) main script
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const main=scripts.reduce((a,b)=>b.length>a.length?b:a,'');

// 2) extract portable core (document-free) between markers
const s=main.indexOf('function bmean(');
const eMark=main.indexOf('END PORTABLE CORE');const e=main.lastIndexOf('/*',eMark);
if(s<0||e<0) throw new Error('core markers not found');
const coreText=main.slice(s,e);
if(/document\.|getElementById/.test(coreText)) throw new Error('core unexpectedly touches DOM');

// 3) extract CLUSTERS array literal via bracket balancing
const ci=main.indexOf('const CLUSTERS=[');
let i=main.indexOf('[',ci),depth=0,end=-1;
for(let k=i;k<main.length;k++){const c=main[k];if(c==='[')depth++;else if(c===']'){depth--;if(depth===0){end=k+1;break;}}}
const clustersText='const CLUSTERS='+main.slice(i,end)+';';

// 4) prove embedded data == our source files
const btdata=fs.readFileSync('btdata.json','utf8').trim();
const data=fs.readFileSync('data.json','utf8').trim();
console.log('embedded btdata matches file :', html.includes(btdata));
console.log('embedded data   matches file :', html.includes(data.slice(0,5000)) && html.includes(data.slice(-5000)));

// 5) run engine with embedded-equivalent data
const DATA=JSON.parse(data), BT=JSON.parse(btdata);
const D=DATA.dates, PE=DATA.pe, SECOF=DATA.sector_of, N=D.length;
const fn=new Function('DATA','D','PE','SECOF','N','BT', clustersText+'\n'+coreText+'\nreturn {btPrep,meanIC};');
const {btPrep,meanIC}=fn(DATA,D,PE,SECOF,N,BT);
const C=btPrep();

const r=JSON.parse(fs.readFileSync('bt_results.json','utf8'));
let pass=0,fail=0;
function chk(name,got,exp,tol){const ok=Math.abs(got-exp)<=tol;console.log(`${ok?'  ok ':' FAIL'}  ${name}: got ${(+got).toFixed(3)}  exp ${exp}`);ok?pass++:fail++;}

// pair IC all horizons
for(const h of [1,3,6,12]){const ic=meanIC(C.pmPair[h],'ls',5);chk(`pair_ic[${h}].ic`,ic.ic,r.pair_ic[h].ic,0.002);chk(`pair_ic[${h}].t`,ic.t,r.pair_ic[h].t,0.05);}
// single-name IC
for(const h of [1,3,6,12]){const ic=meanIC(C.pmSN[h],'rr',6);chk(`sn_ic[${h}].ic`,ic.ic,r.sn_ic[h].ic,0.002);}
// pair conditional @6m (buy-the-discount)
{const o=C.pairObs[6];const disc=o.filter(x=>x.z<-1).map(x=>x.ls);const dm=disc.reduce((a,x)=>a+x,0)/disc.length*100;
 const dh=100*disc.filter(x=>x>0).length/disc.length;
 chk('pair_cond[6].dm (disc mean LS %)',dm,r.pair_cond['6'].dm,0.05);
 chk('pair_cond[6].dn (N)',disc.length,r.pair_cond['6'].dn,0);
 chk('pair_cond[6].dh (hit %)',dh,r.pair_cond['6'].dh,1);}
// portfolio
chk('pair_port.sharpe',C.port.sharpe,r.pair_port.sharpe,0.02);
chk('pair_port.mean %',C.port.mean*100,r.pair_port.mean,0.02);
chk('pair_port.vol %',C.port.vol*100,r.pair_port.vol,0.02);
chk('pair_port.n',C.port.n,r.pair_port.n,0);
chk('pairs count',C.pairs.length,r.meta.pairs,0);


{const RHO=0.5;for(const h of [1,3,6,12]){const disc=C.pairObs[h].filter(x=>x.z<-1);
  const tc=disc.filter(x=>x.rho<=-RHO),rb=disc.filter(x=>x.rho>-RHO);const R=r.trap.disc[h];
  const mm=v=>v.length?+(v.reduce((a,x)=>a+x.ls,0)/v.length*100).toFixed(2):null;
  const hh=v=>v.length?Math.round(100*v.filter(x=>x.ls>0).length/v.length):null;
  chk('trap['+h+'].tc.m',mm(tc),R.tc.m,0.02);chk('trap['+h+'].tc.h',hh(tc),R.tc.h,1);chk('trap['+h+'].rb.m',mm(rb),R.rb.m,0.02);chk('trap['+h+'].rb.n',rb.length,R.rb.n,0);}}
{const TX=10,BOR=50;const net=C.portSeries.map((p,i)=>p.gret-TX/1e4*C.turn[i]-BOR/1e4/12*C.shortg[i]);
 const me=a=>a.reduce((s,x)=>s+x,0)/a.length,sd=a=>{const m=me(a);return Math.sqrt(a.reduce((s,x)=>s+(x-m)*(x-m),0)/a.length);};
 const ns=sd(net)>0?me(net)/sd(net)*Math.sqrt(12):NaN;
 chk('cost.net.sharpe',+ns.toFixed(2),r.cost.net_10_50.sharpe,0.02);
 chk('cost.turn',+me(C.turn).toFixed(3),r.cost.turn,0.02);
 chk('cost.gross.sharpe',+C.port.sharpe.toFixed(2),r.cost.gross.sharpe,0.02);}

console.log(`\n${fail===0?'✅ ALL CHECKS PASSED':'❌ '+fail+' FAILED'} (${pass} passed)`);
