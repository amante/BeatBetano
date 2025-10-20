import React,{useMemo} from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { LS_KEYS, load, fmtCurrency } from './lib'
export default function BankrollChart({ currency, starting }){
  const data=useMemo(()=>{ const lg=load(LS_KEYS.ledger,[]); const rows=[...lg].sort((a,b)=> new Date(a.ts)-new Date(b.ts)); let acc=Number(starting||0); const s=rows.map(r=>{ acc += Number(r.amount||0); return { date:new Date(r.ts).toLocaleDateString(), balance: acc } }); return s.length? s: [{date:new Date().toLocaleDateString(), balance: acc}] },[starting])
  return <div className="w-full h-64"><ResponsiveContainer width="100%" height="100%"><LineChart data={data}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="date"/><YAxis tickFormatter={v=>fmtCurrency(v,currency)}/><Tooltip formatter={v=>fmtCurrency(v,currency)}/><Line type="monotone" dataKey="balance" stroke="#6366f1" strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer></div>
}
