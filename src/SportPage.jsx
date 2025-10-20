import React,{useState} from 'react'
import * as XLSX from 'xlsx'
import { getSettings, toDecimalOdds, pushActivity } from './lib'
import { useNavigate, useParams } from 'react-router-dom'
export default function SportPage(){
  const { sport } = useParams()
  const [rows,setRows]=useState([])
  const [info,setInfo]=useState('')
  const nav=useNavigate(); const settings=getSettings()
  const onImport=async(file)=>{ if(!file) return; const buf=await file.arrayBuffer(); const wb=XLSX.read(new Uint8Array(buf),{type:'array'}); const name=wb.SheetNames[0]; const data=XLSX.utils.sheet_to_json(wb.Sheets[name],{defval:''}); setRows(data); setInfo(`Cargadas ${data.length} filas desde "${name}". Columnas esperadas: event, market, selection, odds, oddsFormat`) }
  const addToSlip=(r)=>{ const fmt=String(r.oddsFormat||settings.oddsFormat||'american').toLowerCase(); const dec=toDecimalOdds(r.odds,fmt); if(!dec||dec<=1) return alert('Cuota inválida en la fila.'); const leg={ id:crypto.randomUUID(), sport:sport.toUpperCase(), league:r.league||'', event:r.event||'', market:r.market||'Custom', selection:r.selection||'', oddsDec:Number(dec.toFixed(6)), oddsFmt:fmt, oddsRaw:String(r.odds), oddsLabel: fmt==='decimal'? dec.toFixed(2): String(r.odds) }; const draft=JSON.parse(localStorage.getItem('beatbetano_slip_draft')||'[]'); draft.push(leg); localStorage.setItem('beatbetano_slip_draft', JSON.stringify(draft)); pushActivity(`Leg añadida desde cartilla ${sport.toUpperCase()}: ${leg.event} • ${leg.market}`) }
  const addAll=()=>{ rows.forEach(addToSlip); alert('Cartilla enviada al Bet Builder.'); nav('/builder') }
  return (<div className="max-w-6xl mx-auto px-4 py-6 space-y-4">
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <h2 className="font-semibold mb-2">Cartillas • {sport?.toUpperCase()}</h2>
      <p className="text-sm text-slate-600 mb-3">Sube un XLSX con columnas: <code>event</code>, <code>market</code>, <code>selection</code>, <code>odds</code>, <code>oddsFormat</code> (american|decimal|fractional). Opcional: <code>league</code>.</p>
      <input type="file" accept=".xlsx" onChange={e=>onImport(e.target.files?.[0])} className="border rounded-lg px-3 py-2" />
      {info && <p className="text-xs text-slate-500 mt-2">{info}</p>}
    </div>
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3"><h3 className="font-medium">Vista previa</h3><div className="flex gap-2"><button onClick={addAll} className="px-3 py-2 rounded-lg bg-indigo-600 text-white">Añadir todo al Bet Builder</button><button onClick={()=>nav('/builder')} className="px-3 py-2 rounded-lg border">Ir al Bet Builder</button></div></div>
      <div className="overflow-auto"><table className="w-full text-sm"><thead className="text-left text-slate-500"><tr><th className="py-2 pr-3">Evento</th><th className="py-2 pr-3">Mercado</th><th className="py-2 pr-3">Selección</th><th className="py-2 pr-3">Cuota</th><th className="py-2 pr-3">Formato</th><th className="py-2">Acciones</th></tr></thead><tbody>{rows.map((r,i)=>(<tr key={i} className="border-t"><td className="py-2 pr-3">{r.event}</td><td className="py-2 pr-3">{r.market}</td><td className="py-2 pr-3">{r.selection}</td><td className="py-2 pr-3">{r.odds}</td><td className="py-2 pr-3">{r.oddsFormat||'american'}</td><td className="py-2"><button onClick={()=>addToSlip(r)} className="px-2 py-1 text-xs rounded-lg border">Añadir</button></td></tr>))}</tbody></table></div>
    </div>
  </div>)
}
