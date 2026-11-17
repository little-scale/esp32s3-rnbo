import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
const html=readFileSync(new URL('../../firmware/components/player_remote/web/index.html',import.meta.url),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const settle=()=>new Promise(r=>setImmediate(r));
async function open(options={}){
 const ids=new Map(),timers=new Map(),requests=[];
 class Element{constructor(tag='div'){this.tag=tag;this.children=[];this.events={};this.value='';this.textContent='';this.style={setProperty(k,v){this[k]=v;}};}append(...e){this.children.push(...e);}replaceChildren(...e){this.children=e;}setAttribute(){}addEventListener(name,fn){this.events[name]=fn;}fire(name){this.events[name]?.();}}
 for(const id of ['patch','board','status','retry','params'])ids.set(id,new Element());
 const doc={hidden:false,activeElement:null,getElementById:id=>ids.get(id),createElement:tag=>new Element(tag),addEventListener(name,fn){this[name]=fn;}};
 let gen=5,playing=true,values=[[440,.2],[1,.5]];
 const schema=()=>({valid:true,generation:gen,device_id:'001122334455',patch:'Test',token:'token',osc_port:1234,parameters:options.parameters||[{id:'cutoff',index:0,name:'Cutoff <script>',min:20,max:20000,steps:0},{id:'mode',index:1,name:'Mode',min:0,max:2,steps:3,enum_values:['a','b','c']}]});
 const fetch=async(path,opt={})=>{requests.push({path,opt});let body;
  if(path==='/api/schema')body=schema();else if(path==='/api/values')body={generation:gen,playing,maintenance:false,values,dropped:0,rejected:0};else if(path==='/api/parameter'){const p=JSON.parse(opt.body);assert.equal(p.generation,gen);assert.equal(opt.headers['X-RNBO-Control'],'token');body={queued:true};}else throw Error(path);
  return{ok:true,json:async()=>body};};
 vm.runInNewContext(code,{document:doc,location:{hostname:'192.168.0.101'},fetch,Map,Number,Error,TextEncoder,console,setInterval:(fn,n)=>timers.set(n,fn),setTimeout:fn=>{Promise.resolve().then(fn);}});
 await settle();await settle();
 return{ids,doc,requests,timers,setPlaying:v=>playing=v,setGeneration:v=>gen=v,setValues:v=>values=v};
}
test('sliders and typed values share sender pacing; numeric values reflect actual readbacks',async()=>{
 const x=await open();const article=x.ids.get('params').children[0],row=article.children[1],slider=row.children[0],number=row.children[1];
 assert.equal(article.children[0].textContent,'Cutoff <script>');assert.equal(number.value,440);assert.equal(slider.value,.2);
 for(let i=0;i<100;++i){slider.value=i/100;slider.fire('input');}
 assert.equal(x.requests.filter(r=>r.path==='/api/parameter').length,0);
 await x.timers.get(20)();let posts=x.requests.filter(r=>r.path==='/api/parameter');assert.equal(posts.length,1);
 let b=JSON.parse(posts[0].opt.body);assert.equal(b.updates.length,1);assert.equal(b.updates[0].value,.99);assert.equal(b.updates[0].normalized,true);
 number.value='1200';number.fire('change');await x.timers.get(20)();posts=x.requests.filter(r=>r.path==='/api/parameter');b=JSON.parse(posts.at(-1).opt.body);assert.equal(b.updates[0].value,1200);assert.equal(b.updates[0].normalized,false);
 x.setValues([[1200,.3],[2,1]]);await x.timers.get(200)();assert.equal(number.value,1200);assert.equal(slider.value,.3);
});
test('enum inputs preserve repeated choices; hidden tabs stop polling and sends; paused controls disable',async()=>{
 const x=await open();const row=x.ids.get('params').children[1].children[1],select=row.children[2];
 select.value='b';select.fire('change');select.fire('change');await x.timers.get(20)();const b=JSON.parse(x.requests.at(-1).opt.body);assert.equal(b.updates.length,2);assert.equal(b.updates[0].value,'b');
 x.doc.hidden=true;const before=x.requests.length;await x.timers.get(200)();await x.timers.get(20)();assert.equal(x.requests.length,before);
 x.doc.hidden=false;x.setPlaying(false);await x.timers.get(200)();assert.equal(row.children[0].disabled,true);
});
test('generation changes rebuild controls and discard unsent values',async()=>{
 const x=await open();const slider=x.ids.get('params').children[0].children[1].children[0];slider.value=.8;slider.fire('input');x.setGeneration(6);await x.timers.get(200)();await settle();await settle();
 await x.timers.get(20)();assert.equal(x.requests.filter(r=>r.path==='/api/parameter').length,0);assert.equal(x.requests.filter(r=>r.path==='/api/schema').length,2);
});
test('browser batches respect UTF-8 request limits for long escaped IDs',async()=>{
 const parameters=Array.from({length:8},(_,i)=>({id:'"'.repeat(180)+i,index:i,name:'Parameter '+i,min:0,max:1,steps:0}));
 const x=await open({parameters});
 for(const a of x.ids.get('params').children){const slider=a.children[1].children[0];slider.value=.8;slider.fire('input');}
 await x.timers.get(20)();await x.timers.get(20)();
 const writes=x.requests.filter(r=>r.path==='/api/parameter');
 assert.equal(writes.length,2);assert.equal(writes.reduce((n,r)=>n+JSON.parse(r.opt.body).updates.length,0),8);
 for(const r of writes)assert.ok(new TextEncoder().encode(r.opt.body).length<=2048);
});
