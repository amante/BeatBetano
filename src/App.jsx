import React,{useEffect,useMemo,useState} from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import { Settings, Wallet, Upload, BarChart3, Dice5, Plus, Trash2, Check, X, ArrowRight } from 'lucide-react'
import * as XLSX from 'xlsx'
import BankrollChart from './BankrollChart'
import SportPage from './SportPage'
import EnvCheck from './EnvCheck'
import { VERSION, LS_KEYS, save, load, nowISO, getSettings, setSettings, fmtCurrency, pushActivity, parlayDecimal, toDecimalOdds, decimalToAmerican, toFraction } from './lib'

function Header({ currency, setCurrency, oddsFormat, setOddsFormat }){
  return (<header className="border-b bg-white sticky top-0 z-10">
    <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
      <Link to="/" className="flex items-center gap-2">
        <div className="w-9 h-9 rounded-xl bg-indigo-600/90 text-white grid place-items-center font-bold">B</div>
        <div><h1 className="text-xl font-semibold leading-none">BeatBetano</h1><p className="text-xs text-slate-500">Gestor de Apuestas • <span>{VERSION}</span></p></div>
      </Link>
      <div className="flex items-center gap-2">
        <select value={currency} onChange={e=>setCurrency(e.target.value)} className="border rounded-lg px-3 py-2 text-sm"><option value="CLP">CLP $</option><option value="USD">USD $</option><option value="EUR">EUR €</option></select>
        <select value={oddsFormat} onChange={e=>setOddsFormat(e.target.value)} className="border rounded-lg px-3 py-2 text-sm"><option value="american">American (-110)</option><option value="decimal">Decimal (1.91)</option><option value="fractional">Fraccional (10/11)</option></select>
        <button onClick={()=>{ if(confirm('Esto eliminará tus datos locales. ¿Continuar?')) { Object.values(LS_KEYS).forEach(k=>localStorage.removeItem(k)); location.reload(); }}} className="px-3 py-2 text-sm rounded-lg border hover:bg-slate-50">Reset</button>
      </div>
    </div>
    <nav className="max-w-6xl mx-auto px-4 pb-2 flex gap-2 flex-wrap">
      <NavButton to="/" icon={BarChart3} label="Dashboard" />
      <NavButton to="/builder" icon={Dice5} label="Bet Builder" />
      <NavButton to="/bets" icon={Upload} label="Apuestas" />
      <NavButton to="/bankroll" icon={Wallet} label="Banca" />
      <NavButton to="/import" icon={Upload} label="Import/Export" />
      <NavButton to="/about" icon={Settings} label="Acerca de" />
      <NavButton to="/env" icon={Settings} label="EnvCheck" />
    </nav>
  </header>)
}
function NavButton({to,icon:Icon,label}){ return <Link to={to} className="px-3 py-2 rounded-lg border bg-white hover:bg-slate-50 inline-flex items-center gap-2">{Icon?<Icon size={16}/>:null}{label}</Link> }

function Home({ currency, bets, ledger, starting }){
  const openCount=useMemo(()=> bets.filter(b=>b.status==='OPEN').length, [bets])
  const roi=useMemo(()=>{ const settled=bets.filter(b=> b.status==='WON'||b.status==='LOST'); const stakeSum=settled.reduce((a,b)=>a+b.stake,0); const retSum=settled.reduce((a,b)=>a+(b.status==='WON'?b.payout:0),0); return stakeSum>0?((retSum-stakeSum)/stakeSum)*100:0 },[bets])
  const cards=[{key:'nfl',title:'NFL',desc:'Props, parlays y cartillas NFL',to:'/nfl'},{key:'nhl',title:'NHL',desc:'Shots, puntos y especiales NHL',to:'/nhl'},{key:'nba',title:'NBA',desc:'Puntos, rebotes, asistencias NBA',to:'/nba'},{key:'tenis',title:'Tenis',desc:'Aces, breaks y set betting',to:'/tenis'}]
  return (<main className="max-w-6xl mx-auto px-4 py-6 space-y-8">
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{cards.map(c=>(<Link to={c.to} key={c.key} className="rounded-2xl bg-white p-5 shadow-sm hover:shadow-md transition-shadow"><div className="flex items-center justify-between"><h3 className="font-semibold">{c.title}</h3><ArrowRight size={18}/></div><p className="text-sm text-slate-600 mt-1">{c.desc}</p><p className="text-xs text-slate-500 mt-3">Ir a funcionalidades →</p></Link>))}</div>
    <div className="grid md:grid-cols-3 gap-4">
      <div className="rounded-2xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">Banca actual</p><p className="text-2xl font-semibold">{fmtCurrency(starting + ledger.reduce((a,x)=> a+Number(x.amount||0),0), currency)}</p></div>
      <div className="rounded-2xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">Apuestas abiertas</p><p className="text-2xl font-semibold">{openCount}</p></div>
      <div className="rounded-2xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">ROI histórico</p><p className="text-2xl font-semibold">{(roi>=0?'+':'')+roi.toFixed(2)}%</p></div>
    </div>
    <div className="rounded-2xl bg-white p-5 shadow-sm"><h2 className="font-semibold mb-3">Evolución de banca</h2><BankrollChart currency={currency} starting={starting} /></div>
    <div className="rounded-2xl bg-white p-5 shadow-sm"><h2 className="font-semibold mb-3">Actividad reciente</h2><ul className="space-y-2 text-sm text-slate-700">{load(LS_KEYS.activity,[]).map(a=><li key={a.ts}>{new Date(a.ts).toLocaleString()} • {a.msg}</li>)}</ul></div>
  </main>)
}

function Builder({ currency }){
  const settings=getSettings()
  const [slip,setSlip]=useState(load(LS_KEYS.slipDraft,[]))
  const [stake,setStake]=useState('')
  useEffect(()=> save(LS_KEYS.slipDraft,slip),[slip])
  const [f,setF]=useState({ sport:'NFL', league:'', event:'', market:'Moneyline', selection:'', legOddsFormat: settings.oddsFormat || 'american', odds:'' })
  const combinedDec=useMemo(()=> slip.length? parlayDecimal(slip):0, [slip])
  const combinedLabel=useMemo(()=>{ if(!combinedDec||combinedDec<=1) return '—'; if((settings.oddsFormat||'american')==='decimal') return combinedDec.toFixed(2); if((settings.oddsFormat||'american')==='fractional') return toFraction(combinedDec); const a=decimalToAmerican(combinedDec); return a!=null?(a>0?`+${a}`:`${a}`):combinedDec.toFixed(2) },[combinedDec,settings.oddsFormat])
  const payout=useMemo(()=>{ const st=Number(stake||0); return (combinedDec && st>0)? st*combinedDec : 0 },[combinedDec,stake])
  const addLeg=()=>{ if(!f.event||!f.odds) return alert('Completa al menos el evento y la cuota.'); const dec=toDecimalOdds(f.odds,f.legOddsFormat); if(!dec||dec<=1) return alert('Cuota inválida.'); const leg={ id:crypto.randomUUID(), sport:f.sport, league:f.league, event:f.event, market:f.market, selection:f.selection, oddsDec:Number(dec.toFixed(6)), oddsFmt:f.legOddsFormat, oddsRaw:f.odds, oddsLabel:f.legOddsFormat==='decimal'?dec.toFixed(2):f.odds }; setSlip(s=>[...s,leg]); setF({...f, selection:'', odds:''}) }
  return (<main className="max-w-6xl mx-auto px-4 py-6 space-y-8">
    <div className="rounded-2xl bg-white p-5 shadow-sm"><h2 className="font-semibold mb-4">Bet Builder</h2>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3"><div><label className="text-xs text-slate-500">Deporte</label><select value={f.sport} onChange={e=>setF({...f, sport:e.target.value})} className="w-full border rounded-lg px-3 py-2"><option>NFL</option><option>NHL</option><option>NBA</option><option>Fútbol</option><option>Tenis</option><option>Otro</option></select></div><div><label className="text-xs text-slate-500">Liga</label><input value={f.league} onChange={e=>setF({...f, league:e.target.value})} className="w-full border rounded-lg px-3 py-2" placeholder="Ej: Week 7 / Premier / ATP 500" /></div></div>
          <div><label className="text-xs text-slate-500">Evento</label><input value={f.event} onChange={e=>setF({...f, event:e.target.value})} className="w-full border rounded-lg px-3 py-2" placeholder="Local vs Visita / Jugador vs Jugador" /></div>
          <div className="grid grid-cols-2 gap-3"><div><label className="text-xs text-slate-500">Mercado</label><select value={f.market} onChange={e=>setF({...f, market:e.target.value})} className="w-full border rounded-lg px-3 py-2"><option>Moneyline</option><option>Spread</option><option>Total</option><option>Jugador - Prop</option><option>Custom</option></select></div><div><label className="text-xs text-slate-500">Selección</label><input value={f.selection} onChange={e=>setF({...f, selection:e.target.value})} className="w-full border rounded-lg px-3 py-2" placeholder="Ej: Over 5.5 / DK Metcalf 60+ yds" /></div></div>
          <div className="grid grid-cols-3 gap-3"><div><label className="text-xs text-slate-500">Formato cuota</label><select value={f.legOddsFormat} onChange={e=>setF({...f, legOddsFormat:e.target.value})} className="w-full border rounded-lg px-3 py-2"><option value="american">American (-110)</option><option value="decimal">Decimal (1.91)</option><option value="fractional">Fraccional (10/11)</option></select></div><div className="col-span-2"><label className="text-xs text-slate-500">Cuota</label><input value={f.odds} onChange={e=>setF({...f, odds:e.target.value})} className="w-full border rounded-lg px-3 py-2" placeholder="-110 / 1.91 / 10/11" /></div></div>
          <button onClick={addLeg} className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 inline-flex items-center gap-2"><Plus size={16}/>Agregar leg</button>
        </div>
        <div className="space-y-4">
          <div className="rounded-xl border p-3"><h3 className="font-medium mb-2">Slip actual</h3><ul className="text-sm space-y-2">{(slip).map((leg,idx)=>(<li key={leg.id} className="border rounded-lg p-2 flex items-center justify-between gap-2"><div className="text-sm"><div className="font-medium">{leg.event}</div><div className="text-xs text-slate-500">{leg.sport} • {leg.league} • {leg.market} • {leg.selection}</div><div className="text-xs">Cuota: {leg.oddsLabel}</div></div><button onClick={()=> setSlip(s=> s.filter((_,i)=> i!==idx))} className="px-2 py-1 text-xs rounded-lg border inline-flex items-center gap-1"><Trash2 size={14}/>Quitar</button></li>))}</ul><div className="flex items-center justify-between mt-3 text-sm"><span>Cuota combinada</span><span className="font-semibold">{(!combinedDec||combinedDec<=1)?'—': ((getSettings().oddsFormat||'american')==='decimal'? combinedDec.toFixed(2): (getSettings().oddsFormat||'american')==='fractional'? (()=>{
            const x=Number(combinedDec); const v=x-1,den=1000; const num=Math.round(v*den); const g=(a,b)=>b?g(b,a%b):a; const m=g(num,den); return `${Math.round(num/m)}/${Math.round(den/m)}`
          })() : ( ()=>{ const x=Number(combinedDec); if(!isFinite(x)||x<=1) return '—'; const val = x>=2? Math.round((x-1)*100) : -Math.round(100/(x-1)); return val>0?`+${val}`:`${val}` })() )}</span></div></div>
          <StakeBox slip={slip} currency={currency} combinedDec={combinedDec} />
        </div>
      </div>
    </div>
  </main>)
}

function StakeBox({ slip, currency, combinedDec }){
  const [stake,setStake]=useState('')
  const [bets,setBets]=useState(load(LS_KEYS.bets,[]))
  useEffect(()=> save(LS_KEYS.bets,bets),[bets])
  const payout=useMemo(()=>{ const st=Number(stake||0); return (combinedDec && st>0)? st*combinedDec : 0 },[combinedDec,stake])
  const saveBet=()=>{ const st=Number(stake||0); if(!slip.length||st<=0) return alert('Agrega legs y un stake válido.'); const b={ id:crypto.randomUUID(), ts:nowISO(), status:'OPEN', legs:slip, stake:st, oddsDec:Number(combinedDec.toFixed(6)), payout:Number((st*combinedDec).toFixed(2)), note:'' }; setBets(bs=>[b,...bs]); pushActivity(`Apuesta creada (${b.legs.length} legs) por ${fmtCurrency(st,currency)}.`); save(LS_KEYS.slipDraft,[]); alert('Apuesta guardada.') }
  return (<div className="grid grid-cols-2 gap-3">
    <div><label className="text-xs text-slate-500">Stake</label><input value={stake} onChange={e=>setStake(e.target.value)} type="number" min="0" step="1" className="w-full border rounded-lg px-3 py-2" placeholder="10000" /></div>
    <div><label className="text-xs text-slate-500">Retorno estimado</label><div className="h-10 grid place-items-center border rounded-lg text-sm">{payout? fmtCurrency(payout,currency): '—'}</div></div>
    <div className="col-span-2 flex gap-2"><button onClick={saveBet} className="px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 inline-flex items-center gap-2"><Check size={16}/>Guardar apuesta</button><Link to="/bets" className="px-4 py-2 rounded-lg border inline-flex items-center gap-2"><X size={16}/>Ir a Apuestas</Link></div>
  </div>)
}

function Bets(){
  const [bets,setBets]=useState(load(LS_KEYS.bets,[]))
  const [statusFilter,setStatusFilter]=useState('ALL')
  const [query,setQuery]=useState('')
  useEffect(()=> save(LS_KEYS.bets,bets),[bets])
  const [ledger,setLedger]=useState(load(LS_KEYS.ledger,[]))
  const addLedger=(amount,type,note)=>{ const row={ id:crypto.randomUUID(), ts:nowISO(), amount:Number(amount||0), type, note:note||'' }; setLedger(lg=>[row,...lg]) }
  useEffect(()=> save(LS_KEYS.ledger,ledger),[ledger])
  const settle=(id,type)=>{ setBets(bs=>{ const i=bs.findIndex(x=>x.id===id); if(i===-1) return bs; const b={...bs[i]}; if(b.status!=='OPEN'){ alert('Ya liquidada.'); return bs } if(type==='WON'){ b.status='WON'; const delta=b.payout-b.stake; addLedger(delta,'Bet WON',`Apuesta ${b.id}`); pushActivity(`Apuesta GANADA: ${fmtCurrency(delta)}`) } else if(type==='LOST'){ b.status='LOST'; addLedger(-b.stake,'Bet LOST',`Apuesta ${b.id}`); pushActivity(`Apuesta PERDIDA: ${fmtCurrency(-b.stake)}`) } else if(type==='VOID'){ b.status='VOID'; pushActivity('Apuesta VOID') } const copy=[...bs]; copy[i]=b; return copy }) }
  const delBet=(id)=>{ if(!confirm('¿Borrar apuesta?')) return; setBets(bs=>bs.filter(b=>b.id!==id)); pushActivity('Apuesta borrada.') }
  return (<main className="max-w-6xl mx-auto px-4 py-6 space-y-8"><div className="rounded-2xl bg-white p-5 shadow-sm"><div className="flex items-center justify-between mb-3"><h2 className="font-semibold">Apuestas</h2><div className="flex gap-2"><select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} className="border rounded-lg px-3 py-2 text-sm"><option value="ALL">Todas</option><option value="OPEN">Abiertas</option><option value="WON">Ganadas</option><option value="LOST">Perdidas</option><option value="VOID">Void</option></select><input value={query} onChange={e=>setQuery(e.target.value)} className="border rounded-lg px-3 py-2 text-sm" placeholder="Buscar…" /></div></div><div className="overflow-auto"><table className="w-full text-sm"><thead className="text-left text-slate-500"><tr><th className="py-2 pr-3">Fecha</th><th className="py-2 pr-3">Detalle</th><th className="py-2 pr-3">Stake</th><th className="py-2 pr-3">Cuota</th><th className="py-2 pr-3">Retorno</th><th className="py-2 pr-3">Estado</th><th className="py-2">Acciones</th></tr></thead><tbody>{bets.filter(b=>{ const ok=(statusFilter==='ALL')||b.status===statusFilter; const text=(b.legs.map(l=>[l.event,l.market,l.selection].join(' ')).join(' | ')+' '+(b.note||'')).toLowerCase(); const okQ=!query || text.includes(query.toLowerCase()); return ok && okQ; }).map(b=>(<tr key={b.id} className="border-t align-top"><td className="py-2 pr-3 whitespace-nowrap">{new Date(b.ts).toLocaleString()}</td><td className="py-2 pr-3" dangerouslySetInnerHTML={{__html:b.legs.map(l=>`${l.event} • ${l.market} • ${l.selection}`).join('<br/>')}} /><td className="py-2 pr-3 whitespace-nowrap">{fmtCurrency(b.stake)}</td><td className="py-2 pr-3">{b.oddsDec.toFixed(2)}</td><td className="py-2 pr-3 whitespace-nowrap">{fmtCurrency(b.payout)}</td><td className="py-2 pr-3"><span className={`inline-flex items-center px-2 py-1 text-xs rounded-lg border ${b.status==='OPEN'?'':b.status==='WON'?'bg-emerald-50 border-emerald-300':b.status==='VOID'?'bg-amber-50 border-amber-300':'bg-rose-50 border-rose-300'}`}>{b.status}</span></td><td className="py-2 whitespace-nowrap"><div className="flex gap-2"><button onClick={()=>settle(b.id,'WON')} className="px-2 py-1 text-xs rounded-lg border">Win</button><button onClick={()=>settle(b.id,'LOST')} className="px-2 py-1 text-xs rounded-lg border">Loss</button><button onClick={()=>settle(b.id,'VOID')} className="px-2 py-1 text-xs rounded-lg border">Void</button><button onClick={()=>delBet(b.id)} className="px-2 py-1 text-xs rounded-lg border">Borrar</button></div></td></tr>))}</tbody></table></div></div></main>)
}

function Bankroll(){
  const [starting,setStarting]=useState(Number(localStorage.getItem(LS_KEYS.starting)||0))
  const [ledger,setLedger]=useState(load(LS_KEYS.ledger,[]))
  useEffect(()=> save(LS_KEYS.ledger,ledger),[ledger])
  const addLedger=(amount,type,note)=>{ const row={ id:crypto.randomUUID(), ts:nowISO(), amount:Number(amount||0), type, note:note||'' }; setLedger(lg=>[row,...lg]) }
  return (<main className="max-w-6xl mx-auto px-4 py-6 space-y-8"><div className="rounded-2xl bg-white p-5 shadow-sm"><h2 className="font-semibold">Banca</h2><div className="grid md:grid-cols-3 gap-3"><div className="space-y-2"><label className="text-xs text-slate-500">Saldo inicial</label><input value={starting} onChange={e=>{ const v=Number(e.target.value||0); setStarting(v); localStorage.setItem(LS_KEYS.starting,String(v)) }} type="number" className="w-full border rounded-lg px-3 py-2" placeholder="0" /></div><BankMovement onAdd={(amt)=>{ const n=Number(amt||0); if(!n) return; addLedger(n, n>0?'Depósito':'Retiro','') }}/><div className="space-y-2"><label className="text-xs text-slate-500">Saldo actual</label><div className="h-10 grid place-items-center border rounded-lg">{fmtCurrency(starting + ledger.reduce((a,x)=> a+Number(x.amount||0),0))}</div></div></div><div className="mt-4"><BankrollChart currency={getSettings().currency} starting={starting} /></div><div className="overflow-auto mt-4"><table className="w-full text-sm"><thead className="text-left text-slate-500"><tr><th className="py-2 pr-3">Fecha</th><th className="py-2 pr-3">Tipo</th><th className="py-2 pr-3">Monto</th><th className="py-2 pr-3">Nota</th></tr></thead><tbody>{ledger.map(r=>(<tr key={r.id} className="border-t"><td className="py-2 pr-3 whitespace-nowrap">{new Date(r.ts).toLocaleString()}</td><td className="py-2 pr-3">{r.type}</td><td className="py-2 pr-3 whitespace-nowrap">{fmtCurrency(r.amount)}</td><td className="py-2 pr-3">{r.note||''}</td></tr>))}</tbody></table></div></div></main>)
}
function BankMovement({ onAdd }){ const [n,setN]=useState(''); return (<div className="space-y-2"><label className="text-xs text-slate-500">Movimiento (+ depósito / - retiro)</label><div className="flex gap-2"><input value={n} onChange={e=>setN(e.target.value)} type="number" className="w-full border rounded-lg px-3 py-2" placeholder="100000" /><button onClick={()=>{ const v=Number(n||0); if(!v) return; onAdd(v); setN('') }} className="px-4 py-2 rounded-lg bg-indigo-600 text-white">Agregar</button></div></div>) }

function ImportExport(){
  const [bets,setBets]=useState(load(LS_KEYS.bets,[]))
  const [ledger,setLedger]=useState(load(LS_KEYS.ledger,[]))
  const [starting,setStarting]=useState(Number(localStorage.getItem(LS_KEYS.starting)||0))
  const exportJSON=()=>{ const blob=new Blob([JSON.stringify({version:VERSION,settings:getSettings(),bets,ledger,starting},null,2)],{type:'application/json'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=`beatbetano_backup_${Date.now()}.json`; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),800) }
  const betsToCSV=(arr)=>{ const headers=['id','fecha','estado','legs','stake','oddsDecimal','payout','nota']; const rows=arr.map(b=>[b.id,new Date(b.ts).toLocaleString(),b.status,b.legs.map(l=>`${l.event} | ${l.market} | ${l.selection} | ${l.oddsDec}`).join(' + '),b.stake,b.oddsDec,b.payout,b.note||'']); return [headers,...rows].map(r=>r.map(s=>{ s=String(s??''); return (s.includes('"')||s.includes(',')||s.includes('\n'))? '"'+s.replace(/"/g,'""')+'"' : s }).join(',')).join('\n') }
  const exportCSV=()=>{ const csv=betsToCSV(bets); const blob=new Blob([csv],{type:'text/csv'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=`beatbetano_bets_${Date.now()}.csv`; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),800) }
  const exportXLSX=()=>{ const wb=XLSX.utils.book_new(); const rows=bets.map(b=>({ id:b.id, ts:b.ts, status:b.status, legs:b.legs.map(l=>`${l.event} | ${l.market} | ${l.selection} | ${l.oddsDec}`).join(' + '), stake:b.stake, oddsDec:b.oddsDec, payout:b.payout, note:b.note||'' })); const wsB=XLSX.utils.json_to_sheet(rows); XLSX.utils.book_append_sheet(wb, wsB, 'Bets'); const wsL=XLSX.utils.json_to_sheet(ledger); XLSX.utils.book_append_sheet(wb, wsL, 'Ledger'); const wsS=XLSX.utils.json_to_sheet([{...getSettings(), version:VERSION, starting }]); XLSX.utils.book_append_sheet(wb, wsS, 'Settings'); XLSX.writeFile(wb, `beatbetano_${Date.now()}.xlsx`) }
  const onImport=async(file)=>{ if(!file) return; const name=file.name.toLowerCase(); if(name.endsWith('.json')){ const text=await file.text(); try{ const data=JSON.parse(text); if(data.settings) save(LS_KEYS.settings,data.settings); if(Array.isArray(data.bets)) setBets(data.bets); if(Array.isArray(data.ledger)) setLedger(data.ledger); if(data.starting!=null) setStarting(Number(data.starting)); alert('Importación JSON completa.') }catch{ alert('JSON inválido.') } return } if(name.endsWith('.csv')){ const text=await file.text(); const lines=text.split(/\r?\n/); const rows=lines.slice(1).filter(Boolean).map(line=>line.split(',')); const imported=rows.map(r=>({ id:r[0]||crypto.randomUUID(), ts:new Date(r[1]||Date.now()).toISOString(), status:r[2]||'OPEN', legs:String(r[3]||'').split(' + ').filter(Boolean).map(x=>{ const parts=x.split(' | '); return { event:parts[0]||'', market:parts[1]||'', selection:parts[2]||'', oddsDec:Number(parts[3]||1.0)||1.0 } }), stake:Number(r[4]||0), oddsDec:Number(r[5]||1.0), payout:Number(r[6]||0), note:r[7]||'' })); setBets(imported); alert('Importación CSV completa (Bets).'); return } if(name.endsWith('.xlsx')){ const buf=await file.arrayBuffer(); const wb=XLSX.read(new Uint8Array(buf),{type:'array'}); if(wb.Sheets['Bets']){ const arr=XLSX.utils.sheet_to_json(wb.Sheets['Bets']); const norm=arr.map(b=>({ id:b.id||crypto.randomUUID(), ts:b.ts||nowISO(), status:b.status||'OPEN', legs:String(b.legs||'').split(' + ').filter(Boolean).map(x=>{ const parts=x.split(' | '); return { event:parts[0]||'', market:parts[1]||'', selection:parts[2]||'', oddsDec:Number(parts[3]||1.0)||1.0 } }), stake:Number(b.stake||0), oddsDec:Number(b.oddsDec||1.0), payout:Number(b.payout||0), note:b.note||'' })); setBets(norm) } if(wb.Sheets['Ledger']){ const lg=XLSX.utils.sheet_to_json(wb.Sheets['Ledger']); save(LS_KEYS.ledger,lg) } if(wb.Sheets['Settings']){ const s=XLSX.utils.sheet_to_json(wb.Sheets['Settings'])[0]||{}; if(s.currency||s.oddsFormat) setSettings({ currency:s.currency||getSettings().currency, oddsFormat:s.oddsFormat||getSettings().oddsFormat }); if(s.starting!=null) { localStorage.setItem(LS_KEYS.starting,String(Number(s.starting||0))) } } alert('Importación XLSX completa.'); return } alert('Formato no soportado.') }
  return (<main className="max-w-6xl mx-auto px-4 py-6 space-y-8"><div className="rounded-2xl bg-white p-5 shadow-sm"><div className="flex items-center justify_between mb-3"><h2 className="font-semibold">Importar / Exportar</h2></div><div className="grid md:grid-cols-2 gap-4"><div className="space-y-2"><h3 className="font-medium">Exportar</h3><div className="flex gap-2 flex-wrap"><button onClick={exportJSON} className="px-3 py-2 rounded-lg border">Exportar JSON</button><button onClick={exportCSV} className="px-3 py-2 rounded-lg border">Exportar CSV</button><button onClick={exportXLSX} className="px-3 py-2 rounded-lg border">Exportar XLSX</button></div></div><div className="space-y-2"><h3 className="font-medium">Importar</h3><input onChange={e=>onImport(e.target.files?.[0])} type="file" className="border rounded-lg px-3 py-2 w-full" accept=".json,.csv,.xlsx" /><p className="text-xs text-slate-500">Acepta JSON / CSV / XLSX (hojas: Bets, Ledger, Settings)</p></div></div></div></main>)
}

function About(){ return (<main className="max-w-6xl mx-auto px-4 py-6 space-y-8"><div className="rounded-2xl bg-white p-5 shadow-sm"><h2 className="font-semibold">Acerca de BeatBetano</h2><ul className="text-sm list-disc pl-5 text-slate-700"><li>Cuotas American / Decimal / Fraccional</li><li>Parlays con cálculo automático</li><li>Cartillas por deporte con carga XLSX</li><li>ROI, banca y exportación de datos</li></ul><p className="text-xs text-slate-500 mt-2">Versión {VERSION}</p><p className="text-xs mt-2"><a className="underline" href="/BeatBetano/#/env">Comprobar BASE_URL</a></p></div></main>) }

export default function App(){
  const [currency,setCurrency]=useState(getSettings().currency)
  const [oddsFormat,setOddsFormat]=useState(getSettings().oddsFormat)
  useEffect(()=>{ setSettings({currency,oddsFormat}) },[currency,oddsFormat])
  const [bets]=useState(load(LS_KEYS.bets,[]))
  const [ledger]=useState(load(LS_KEYS.ledger,[]))
  const [starting]=useState(Number(localStorage.getItem(LS_KEYS.starting)||0))
  return (<div className="min-h-screen text-slate-800">
    <Header currency={currency} setCurrency={setCurrency} oddsFormat={oddsFormat} setOddsFormat={setOddsFormat} />
    <Routes>
      <Route path="/" element={<Home currency={currency} bets={bets} ledger={ledger} starting={starting} />} />
      <Route path="/builder" element={<Builder currency={currency} />} />
      <Route path="/bets" element={<Bets />} />
      <Route path="/bankroll" element={<Bankroll />} />
      <Route path="/import" element={<ImportExport />} />
      <Route path="/about" element={<About />} />
      <Route path="/env" element={<EnvCheck />} />
      <Route path="/:sport" element={<SportPage />} />
    </Routes>
  </div>)
}
