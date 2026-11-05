// SPDX-License-Identifier: MIT
// Original lowering for a deliberately explicit embedded dsp.gen core graph.
// Unknown nodes, defaults, resources and ambiguous routes fail before codegen.
const numeric = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
const number = text => { if (!numeric.test(text) || !Number.isFinite(Number(text))) throw Error('Visual Gen requires a finite numeric literal'); return Object.is(Number(text),-0)?'-0.0':String(Number(text)); };
const index = text => { if (!/^[1-9]\d*$/.test(text) || Number(text)>64) throw Error('Visual Gen port index must be 1..64'); return Number(text); };
const boxFields=new Set(['id','maxclass','text','numinlets','numoutlets','patching_rect','outlettype','fontname','fontsize','fontface','linecount','comment','annotation','color','textcolor','bgcolor','hidden','presentation','presentation_rect','style','rnbo_extra_attributes']);
const coreOperators=new Set(['in','out','+','-','*','/','abs','neg','history']);
const binary = new Map([
 ['+','+'],['-','-'],['*','*'],['/','/'],['add','+'],['sub','-'],['mul','*'],['div','/'],
 ['<','<'],['lt','<'],['<=','<='],['lte','<='],['>','>'],['gt','>'],['>=','>='],['gte','>='],['==','=='],['eq','=='],['!=','!='],['neq','!='],
 ['<p','<p'],['ltp','<p'],['<=p','<=p'],['ltep','<=p'],['>p','>p'],['gtp','>p'],['>=p','>=p'],['gtep','>=p'],['==p','==p'],['eqp','==p'],['!=p','!=p'],['neqp','!=p'],
 ['&&','&&'],['and','&&'],['||','||'],['or','||'],['^^','^^'],['xor','^^']
]);
const functions = new Map([
 ...['acos','acosh','asin','asinh','atan','atanh','cos','cosh','sin','sinh','tan','tanh','exp','exp2','log','log2','log10','sqrt','ceil','floor','trunc','fract','sign','fastsin','fastcos','fasttan','fastexp'].map(name=>[name,{name,arity:1}]),
 ['ln',{name:'log',arity:1}],
 ...['pow','atan2','hypot','min','max'].map(name=>[name,{name,arity:2}]),
 ['minimum',{name:'min',arity:2}],['maximum',{name:'max',arity:2}]
]);
// Fully wired forms only. Each GenExpr call site owns its sample-rate state.
const flowFunctions=new Map([
 ...['delta','change','dcblock','phasewrap','pass','fixnan','isnan','mtof','ftom','atodb','dbtoa','t60','t60time'].map(name=>[name,{name,arity:1}]),
 ...['latch','accum','plusequals','absdiff','mod','triangle'].map(name=>[name,{name,arity:2}]),
 ['%',{name:'mod',arity:2}],
 ...['sah','slide','clamp','clip','fold','wrap','mix','smoothstep','interp'].map(name=>[name,{name,arity:3}]),
 ['scale',{name:'scale',arity:5}],
 ['counter',{name:'counter',arity:3,outputs:3}],
 ['cartopol',{name:'cartopol',arity:2,outputs:2}],['poltocar',{name:'poltocar',arity:2,outputs:2}]
]);
const outputVariable=(node,outlet=0)=>outlet===0?node.variable:`${node.variable}_o${outlet}`;
const constants=new Map();
for(const [lower,upper] of [['pi','PI'],['e','E'],['twopi','TWOPI'],['halfpi','HALFPI'],['degtorad','DEGTORAD'],['radtodeg','RADTODEG'],['ln2','LN2'],['ln10','LN10'],['log2e','LOG2E'],['log10e','LOG10E'],['sqrt2','SQRT2'],['sqrt1_2','SQRT1_2'],['invpi','INVPI'],['phi','PHI']]){
 constants.set(lower,upper);constants.set(upper,upper);
}
const unary = new Map([['abs','abs'],['neg','negative']]);
export function lowerVisualGen(document) {
  if (!document || typeof document!=='object' || Array.isArray(document) || !document.patcher) throw Error('Visual Gen needs genpatcher.patcher');
  const graph=document.patcher;
  if (graph.classnamespace!=='dsp.gen' || !Array.isArray(graph.boxes) || !Array.isArray(graph.lines) ||
      graph.boxes.length>512 || graph.lines.length>2048) throw Error('Unsupported or oversized visual Gen graph');
  const nodes=new Map(), allIds=new Set(), histories=new Set(), ins=new Set(), outs=new Set();
  for (const entry of graph.boxes) {
    const b=entry?.box;
    if (!b || typeof b.id!=='string' || !b.id || allIds.has(b.id)) throw Error('Visual Gen box IDs must be unique');
    allIds.add(b.id);
    if (b.patcher || b.genpatcher || b.filename || b.rnbo_abstraction) throw Error('Nested/external visual Gen nodes are not implemented');
    if (b.maxclass==='comment') continue;
    if (Object.keys(b).some(key=>!boxFields.has(key))) throw Error('Unsupported visual Gen node attributes');
    if (b.maxclass!=='newobj' || typeof b.text!=='string' || !b.text.trim() ||
        (b.rnbo_extra_attributes && Object.keys(b.rnbo_extra_attributes).length)) throw Error('Visual Gen core requires plain explicit newobj nodes');
    const [op,...args]=b.text.trim().split(/\s+/), n={id:b.id,op,args,variable:`vg_n${nodes.size}`,inputs:[],inputOutlets:[],arity:0,outputs:1};
    if (op==='in' || op==='out') {
      if (args.length!==1) throw Error('Visual Gen in/out requires one ordinal');
      n.port=index(args[0]);const ports=op==='in'?ins:outs;
      if (ports.has(n.port)) throw Error('Duplicate visual Gen input/output ordinal');ports.add(n.port);
      n.arity=op==='in'?0:1;n.outputs=op==='in'?1:0;
    } else if (binary.has(op)) {
      if (args.length>1) throw Error('Visual Gen binary core supports zero or one fixed operand');
      n.arity=args.length?1:2;if (args.length)n.cold=number(args[0]);
    } else if (unary.has(op)) {
      if (args.length) throw Error('Visual Gen unary core takes no arguments');n.arity=1;
    } else if (functions.has(op)) {
      if(args.length)throw Error('Visual Gen maths functions currently require fully connected inputs');
      n.fn=functions.get(op).name;n.arity=functions.get(op).arity;
    } else if (flowFunctions.has(op)) {
      if(args.length)throw Error('Visual Gen flow functions require fully connected explicit inputs');
      const spec=flowFunctions.get(op);n.fn=spec.name;n.arity=spec.arity;n.outputs=spec.outputs??1;
    } else if (op==='not'||op==='!'||op==='bool') {
      if(args.length)throw Error('Visual Gen unary logic currently requires one connected input');n.arity=1;
    } else if (constants.has(op)||op==='constant') {
      if(op==='constant'){
        if(args.length!==1)throw Error('Visual Gen constant requires one explicit finite literal');n.constant=number(args[0]);
      }else{
        if(args.length)throw Error('Visual Gen named constant takes no arguments');n.constant=constants.get(op);
      }
    } else if (op==='history') {
      n.arity=1;n.initial='0';n.state=`vg_h${nodes.size}`;
      if (args.length>2) throw Error('Unsupported visual Gen history arguments');
      if (args.length===1 && numeric.test(args[0])) n.initial=number(args[0]);
      else if (args.length) {
        if (!/^[A-Za-z_]\w*$/.test(args[0]) || histories.has(args[0])) throw Error('Visual Gen shared/nonnumeric history names are not implemented');
        if (/^(?:vg_|in[0-9]+$|out[0-9]+$)/.test(args[0])) throw Error('Visual Gen history name conflicts with reserved lowering identifiers');
        histories.add(args[0]);n.state=args[0];if (args.length===2)n.initial=number(args[1]);
      }
    } else throw Error(`Unsupported visual Gen core operator: ${op}`);
    for (const [key,expected] of [['numinlets',n.arity],['numoutlets',n.outputs]]) {
      if (b[key]!==undefined && b[key]!==expected) throw Error(`Visual Gen saved ${key} differs from explicit node arity`);
    }
    nodes.set(b.id,n);
  }
  if (!nodes.size || !outs.size || Math.max(...outs)!==outs.size || (ins.size && Math.max(...ins)!==ins.size)) throw Error('Visual Gen ports must be dense and outputs nonempty');
  for (const entry of graph.lines) {
    const line=entry?.patchline, source=line?.source, target=line?.destination;
    if (!line || line.disabled || !Array.isArray(source) || source.length!==2 || !Array.isArray(target) || target.length!==2 ||
        !nodes.has(source[0]) || !nodes.has(target[0]) || !Number.isInteger(source[1]) || !Number.isInteger(target[1])) throw Error('Invalid visual Gen connection');
    const a=nodes.get(source[0]), b=nodes.get(target[0]), slot=target[1];
    if (!a.outputs || source[1]<0 || source[1]>=a.outputs || slot<0 || slot>=b.arity || b.inputs[slot]!==undefined) throw Error('Visual Gen duplicate/fan-in/out-of-range connection');
    b.inputs[slot]=a;b.inputOutlets[slot]=source[1];
  }
  for (const n of nodes.values()) {
    if (n.op==='history') continue; // Unconnected histories hold their initial value.
    for (let i=0;i<n.arity;i++)if (!n.inputs[i]) throw Error('Visual Gen implicit disconnected defaults are not implemented');
  }
  const visited=new Set(), active=new Set(), ordered=[];
  function visit(n) {
    if (visited.has(n.id))return;
    if (active.has(n.id))throw Error('Visual Gen algebraic cycle requires an explicit history');
    active.add(n.id);
    if (n.op!=='history')for (const upstream of n.inputs)visit(upstream);
    active.delete(n.id);visited.add(n.id);ordered.push(n);
  }
  for (const n of nodes.values())visit(n);
  const lines=[];
  for (const n of nodes.values())if (n.op==='history')lines.push(`History ${n.state}(${n.initial});`);
  // Snapshot every old history before any arithmetic or next-state assignment.
  for (const n of nodes.values())if (n.op==='history')lines.push(`${n.variable} = ${n.state};`);
  for (const n of ordered) {
    const input=n.inputs.map((x,i)=>outputVariable(x,n.inputOutlets[i]));
    if (n.op==='history')continue;
    if (n.op==='out')lines.push(`out${n.port} = ${input[0]};`);
    else if (n.op==='in')lines.push(`${n.variable} = in${n.port};`);
    else if (binary.has(n.op))lines.push(`${n.variable} = ${input[0]} ${binary.get(n.op)} ${n.cold??input[1]};`);
    else if (n.constant!==undefined)lines.push(`${n.variable} = ${n.constant};`);
    else if (n.fn)lines.push(`${Array.from({length:n.outputs},(_,i)=>outputVariable(n,i)).join(', ')} = ${n.fn}(${input.join(', ')});`);
    else if (n.op==='not'||n.op==='!')lines.push(`${n.variable} = !${input[0]};`);
    else if (n.op==='bool')lines.push(`${n.variable} = (${input[0]} != 0);`);
    else if (n.op==='neg')lines.push(`${n.variable} = -${input[0]};`);
    else lines.push(`${n.variable} = ${unary.get(n.op)}(${input[0]});`);
  }
  for (const n of nodes.values())if (n.op==='history' && n.inputs[0])lines.push(`${n.state} = ${outputVariable(n.inputs[0],n.inputOutlets[0])};`);
  return {expression:lines.join('\n')+'\n',geninlets:ins.size,genoutlets:outs.size,
    policy:[...nodes.values()].some(n=>flowFunctions.has(n.op))?'embedded-visual-gen-flow-v1':[...nodes.values()].every(n=>coreOperators.has(n.op))?'embedded-visual-gen-core-v1':'embedded-visual-gen-math-v1',nodes:nodes.size,edges:graph.lines.length,
    history_count:[...nodes.values()].filter(n=>n.op==='history').length,operators:[...new Set([...nodes.values()].map(n=>n.op))].sort()};
}
