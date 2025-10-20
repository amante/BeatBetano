import React, { useEffect, useMemo, useState } from 'react'
import { Settings, Wallet, Upload, BarChart3, Dice5, Plus, Trash2, Check, X, AlertCircle } from 'lucide-react'
import * as XLSX from 'xlsx'

// -------- Storage & Keys --------
const VERSION = 'v1.0.0'
const LS_KEYS = {
  bets: 'beatbetano_bets',
  ledger: 'beatbetano_ledger',
  settings: 'beatbetano_settings',
  starting: 'beatbetano_starting',
  activity: 'beatbetano_activity'
}

const save = (k, v) => localStorage.setItem(k, JSON.stringify(v))
const load = (k, f) => JSON.parse(localStorage.getItem(k) || JSON.stringify(f))

// -------- Odds utils --------
const americanToDecimal = (a) => {
  const n = Number(a)
  if (!isFinite(n) || n === 0) return null
  return n > 0 ? 1 + n / 100 : 1 + 100 / Math.abs(n)
}

const fractionalToDecimal = (fr) => {
  const [num, den] = String(fr).split('/').map(Number)
  if (!isFinite(num) || !isFinite(den) || den === 0) return null
  return 1 + num / den
}

const toDecimalOdds = (input, fmt) => {
  if (fmt === 'decimal') {
    const d = Number(input)
    return isFinite(d) && d > 1 ? d : null
  }
  if (fmt === 'american') return americanToDecimal(input)
  if (fmt === 'fractional') return fractionalToDecimal(input)
  return null
}

const decimalToAmerican = (d) => {
  const x = Number(d)
  if (!isFinite(x) || x <= 1) return null
  if (x >= 2) return Math.round((x - 1) * 100)
  return -Math.round(100 / (x - 1))
}

const toFraction = (dec) => {
  const x = Number(dec)
  if (!isFinite(x) || x <= 1) return '—'
  const v = x - 1
  const denom = 1000
  const num = Math.round(v * denom)
  const g = (a,b)=> b? g(b, a%b): a
  const d = g(num, denom)
  return `${Math.round(num/d)}/${Math.round(denom/d)}`
}

// -------- Helpers --------
const nowISO = () => new Date().toISOString()
const pushActivity = (msg) => {
  const list = load(LS_KEYS.activity, [])
  list.unshift({ ts: nowISO(), msg })
  save(LS_KEYS.activity, list.slice(0, 15))
}

const getSettings = () => load(LS_KEYS.settings, { currency: 'CLP', oddsFormat: 'american' })
const setSettings = (p) => { const s = { ...getSettings(), ...p }; save(LS_KEYS.settings, s); return s }

const fmtCurrency = (v, curr) => {
  const map = { CLP: 'es-CL', USD: 'en-US', EUR: 'de-DE' }
  const currency = curr || getSettings().currency
  try {
    return new Intl.NumberFormat(map[currency] || 'es-CL', { style: 'currency', currency }).format(Number(v || 0))
  } catch {
    return (currency + ' ' + Number(v || 0).toFixed(2))
  }
}

const parlayDecimal = (legs) => legs.reduce((p, l) => p * Number(l.oddsDec), 1)

// -------- Components --------
const TabButton = ({ id, label, icon:Icon, active, onClick }) => (
  <button onClick={() => onClick(id)}
    className={`px-3 py-2 rounded-lg border bg-white hover:bg-slate-50 inline-flex items-center gap-2 ${active?'bg-indigo-600 text-white hover:bg-indigo-700 border-indigo-600':''}`}>
    {Icon ? <Icon size={16}/> : null}{label}
  </button>
)

const Section = ({ title, children, right }) => (
  <div className="rounded-2xl bg-white p-5 shadow-sm">
    <div className="flex items-center justify-between mb-3">
      <h2 className="font-semibold">{title}</h2>
      {right}
    </div>
    {children}
  </div>
)

export default function App(){
  const [tab, setTab] = useState('dashboard')

  // header settings
  const [currency, setCurrency] = useState(getSettings().currency)
  const [oddsFormat, setOddsFormat] = useState(getSettings().oddsFormat)

  useEffect(()=>{ setSettings({ currency, oddsFormat }); }, [currency, oddsFormat])

  // slip
  const [slip, setSlip] = useState([])
  const [stake, setStake] = useState('')

  // bets
  const [bets, setBets] = useState(load(LS_KEYS.bets, []))
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [query, setQuery] = useState('')

  // ledger / bankroll
  const [starting, setStarting] = useState(Number(localStorage.getItem(LS_KEYS.starting) || 0))
  const [ledger, setLedger] = useState(load(LS_KEYS.ledger, []))

  useEffect(()=> save(LS_KEYS.bets, bets), [bets])
  useEffect(()=> save(LS_KEYS.ledger, ledger), [ledger])
  useEffect(()=> localStorage.setItem(LS_KEYS.starting, String(Number(starting||0))), [starting])

  const currentBalance = useMemo(()=> starting + ledger.reduce((a,x)=> a + Number(x.amount), 0), [starting, ledger])
  const openCount = useMemo(()=> bets.filter(b => b.status==='OPEN').length, [bets])
  const roi = useMemo(()=>{
    const settled = bets.filter(b=> b.status==='WON' || b.status==='LOST')
    const stakeSum = settled.reduce((a,b)=> a + b.stake, 0)
    const retSum = settled.reduce((a,b)=> a + (b.status==='WON' ? b.payout : 0), 0)
    return stakeSum>0 ? ((retSum - stakeSum)/stakeSum)*100 : 0
  }, [bets])

  // activity
  const [activity, setActivity] = useState(load(LS_KEYS.activity, []))

  const addActivity = (msg) => { pushActivity(msg); setActivity(load(LS_KEYS.activity, [])) }

  // builder fields
  const [f, setF] = useState({
    sport: 'NFL', league: '', event: '', market: 'Moneyline', selection: '',
    legOddsFormat: 'american', odds: ''
  })

  const combinedDec = useMemo(()=> slip.length? parlayDecimal(slip): 0, [slip])

  const combinedLabel = useMemo(()=>{
    if (!combinedDec || combinedDec<=1) return '—'
    if (oddsFormat==='decimal') return combinedDec.toFixed(2)
    if (oddsFormat==='fractional') return toFraction(combinedDec)
    const a = decimalToAmerican(combinedDec)
    return a!=null ? (a>0?`+${a}`:`${a}`) : combinedDec.toFixed(2)
  }, [combinedDec, oddsFormat])

  const payout = useMemo(()=>{
    const st = Number(stake||0)
    return (combinedDec && st>0) ? st*combinedDec : 0
  }, [combinedDec, stake])

  const addLeg = () => {
    if (!f.event || !f.odds) return alert('Completa al menos el evento y la cuota.')
    const dec = toDecimalOdds(f.odds, f.legOddsFormat)
    if (!dec || dec<=1) return alert('Cuota inválida.')
    const leg = {
      id: crypto.randomUUID(),
      sport: f.sport, league: f.league, event: f.event, market: f.market, selection: f.selection,
      oddsDec: Number(dec.toFixed(6)),
      oddsFmt: f.legOddsFormat,
      oddsRaw: f.odds,
      oddsLabel: f.legOddsFormat==='decimal' ? dec.toFixed(2) : f.odds
    }
    setSlip(s => [...s, leg])
    setF({ ...f, selection:'', odds:'' })
  }

  const clearSlip = () => setSlip([])

  const saveBet = () => {
    const st = Number(stake||0)
    if (!slip.length || st<=0) return alert('Agrega legs y un stake válido.')
    const dec = combinedDec
    const b = {
      id: crypto.randomUUID(),
      ts: nowISO(),
      status: 'OPEN',
      legs: slip,
      stake: st,
      oddsDec: Number(dec.toFixed(6)),
      payout: Number((st*dec).toFixed(2)),
      note: ''
    }
    setBets(bs => [b, ...bs])
    addActivity(`Apuesta creada (${b.legs.length} legs) por ${fmtCurrency(st, currency)}.`)
    setSlip([]); setStake(''); setTab('bets')
  }

  const settle = (id, type) => {
    setBets(bs => {
      const idx = bs.findIndex(x=> x.id===id)
      if (idx===-1) return bs
      const b = { ...bs[idx] }
      if (b.status!=='OPEN') { alert('Ya liquidada.'); return bs }
      if (type==='WON') {
        b.status = 'WON'
        const delta = b.payout - b.stake
        addLedger(delta, 'Bet WON', `Apuesta ${b.id}`)
        addActivity(`Apuesta GANADA: ${fmtCurrency(delta, currency)}`)
      } else if (type==='LOST') {
        b.status = 'LOST'
        addLedger(-b.stake, 'Bet LOST', `Apuesta ${b.id}`)
        addActivity(`Apuesta PERDIDA: ${fmtCurrency(-b.stake, currency)}`)
      } else if (type==='VOID') {
        b.status = 'VOID'
        addActivity('Apuesta VOID')
      }
      const copy = [...bs]
      copy[idx] = b
      return copy
    })
  }

  const delBet = (id) => {
    if (!confirm('¿Borrar apuesta?')) return
    setBets(bs => bs.filter(b => b.id!==id))
    addActivity('Apuesta borrada.')
  }

  const addLedger = (amount, type, note) => {
    const row = { id: crypto.randomUUID(), ts: nowISO(), amount: Number(amount||0), type, note: note||'' }
    setLedger(lg => [row, ...lg])
  }

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify({
      version: VERSION,
      settings: getSettings(),
      bets, ledger, starting
    }, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `beatbetano_backup_${Date.now()}.json`
    a.click(); setTimeout(()=> URL.revokeObjectURL(a.href), 800)
  }

  const betsToCSV = (arr) => {
    const headers = ['id','fecha','estado','legs','stake','oddsDecimal','payout','nota']
    const rows = arr.map(b => [
      b.id,
      new Date(b.ts).toLocaleString(),
      b.status,
      b.legs.map(l => `${l.event} | ${l.market} | ${l.selection} | ${l.oddsDec}`).join(' + '),
      b.stake,
      b.oddsDec,
      b.payout,
      b.note || ''
    ])
    return [headers, ...rows].map(r => r.map(s => {
      s = String(s ?? '')
      return (s.includes('"') || s.includes(',') || s.includes('\n')) ? `"${s.replace(/"/g,'""')}"` : s
    }).join(',')).join('\n')
  }

  const exportCSV = () => {
    const csv = betsToCSV(bets)
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `beatbetano_bets_${Date.now()}.csv`
    a.click(); setTimeout(()=> URL.revokeObjectURL(a.href), 800)
  }

  const exportXLSX = () => {
    const wb = XLSX.utils.book_new()
    const betRows = bets.map(b => ({
      id: b.id, ts: b.ts, status: b.status,
      legs: b.legs.map(l => `${l.event} | ${l.market} | ${l.selection} | ${l.oddsDec}`).join(' + '),
      stake: b.stake, oddsDec: b.oddsDec, payout: b.payout, note: b.note || ''
    }))
    const wsB = XLSX.utils.json_to_sheet(betRows); XLSX.utils.book_append_sheet(wb, wsB, 'Bets')
    const wsL = XLSX.utils.json_to_sheet(ledger); XLSX.utils.book_append_sheet(wb, wsL, 'Ledger')
    const wsS = XLSX.utils.json_to_sheet([{ ...getSettings(), version: VERSION, starting }]); XLSX.utils.book_append_sheet(wb, wsS, 'Settings')
    XLSX.writeFile(wb, `beatbetano_${Date.now()}.xlsx`)
  }

  const onImport = async (file) => {
    if (!file) return
    const name = file.name.toLowerCase()
    if (name.endsWith('.json')) {
      const text = await file.text()
      try {
        const data = JSON.parse(text)
        if (data.settings) save(LS_KEYS.settings, data.settings)
        if (Array.isArray(data.bets)) setBets(data.bets)
        if (Array.isArray(data.ledger)) setLedger(data.ledger)
        if (data.starting != null) setStarting(Number(data.starting))
        alert('Importación JSON completa.')
      } catch {
        alert('JSON inválido.')
      }
      return
    }
    if (name.endsWith('.csv')) {
      const text = await file.text()
      const lines = text.split(/\r?\n/)
      const rows = lines.slice(1).filter(Boolean).map(line => line.split(','))
      const imported = rows.map(r => ({
        id: r[0] || crypto.randomUUID(),
        ts: new Date(r[1] || Date.now()).toISOString(),
        status: r[2] || 'OPEN',
        legs: String(r[3] || '').split(' + ').filter(Boolean).map(x => {
          const parts = x.split(' | ')
          return { event: parts[0] || '', market: parts[1] || '', selection: parts[2] || '', oddsDec: Number(parts[3] || 1.0) || 1.0 }
        }),
        stake: Number(r[4] || 0),
        oddsDec: Number(r[5] || 1.0),
        payout: Number(r[6] || 0),
        note: r[7] || ''
      }))
      setBets(imported)
      alert('Importación CSV completa (Bets).')
      return
    }
    if (name.endsWith('.xlsx')) {
      const buf = await file.arrayBuffer()
      const wb = XLSX.read(new Uint8Array(buf), { type: 'array' })
      if (wb.Sheets['Bets']) {
        const arr = XLSX.utils.sheet_to_json(wb.Sheets['Bets'])
        const norm = arr.map(b => ({
          id: b.id || crypto.randomUUID(),
          ts: b.ts || nowISO(),
          status: b.status || 'OPEN',
          legs: String(b.legs || '').split(' + ').filter(Boolean).map(x => {
            const parts = x.split(' | ')
            return { event: parts[0] || '', market: parts[1] || '', selection: parts[2] || '', oddsDec: Number(parts[3] || 1.0) || 1.0 }
          }),
          stake: Number(b.stake || 0),
          oddsDec: Number(b.oddsDec || 1.0),
          payout: Number(b.payout || 0),
          note: b.note || ''
        }))
        setBets(norm)
      }
      if (wb.Sheets['Ledger']) {
        const lg = XLSX.utils.sheet_to_json(wb.Sheets['Ledger'])
        setLedger(lg.map(r => ({ id: r.id || crypto.randomUUID(), ts: r.ts || nowISO(), amount: Number(r.amount || 0), type: r.type || 'Ajuste', note: r.note || '' })))
      }
      if (wb.Sheets['Settings']) {
        const s = XLSX.utils.sheet_to_json(wb.Sheets['Settings'])[0] || {}
        if (s.currency || s.oddsFormat) setSettings({ currency: s.currency || getSettings().currency, oddsFormat: s.oddsFormat || getSettings().oddsFormat })
        if (s.starting != null) setStarting(Number(s.starting || 0))
      }
      alert('Importación XLSX completa.')
      return
    }
    alert('Formato no soportado.')
  }

  return (
    <div className="min-h-screen text-slate-800">
      {/* Header */}
      <header className="border-b bg-white sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-indigo-600/90 text-white grid place-items-center font-bold">B</div>
            <div>
              <h1 className="text-xl font-semibold leading-none">BeatBetano</h1>
              <p className="text-xs text-slate-500">Gestor de Apuestas • <span>{VERSION}</span></p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select value={currency} onChange={e=>setCurrency(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
              <option value="CLP">CLP $</option><option value="USD">USD $</option><option value="EUR">EUR €</option>
            </select>
            <select value={oddsFormat} onChange={e=>setOddsFormat(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
              <option value="american">American (-110)</option>
              <option value="decimal">Decimal (1.91)</option>
              <option value="fractional">Fraccional (10/11)</option>
            </select>
            <button onClick={()=>{ if(confirm('Esto eliminará tus datos locales. ¿Continuar?')) { Object.values(LS_KEYS).forEach(k => localStorage.removeItem(k)); location.reload(); }}} className="px-3 py-2 text-sm rounded-lg border hover:bg-slate-50" title="Reiniciar">
              Reset
            </button>
          </div>
        </div>
        <nav className="max-w-6xl mx-auto px-4 pb-2 flex gap-2 flex-wrap">
          <TabButton id="dashboard" label="Dashboard" icon={BarChart3} active={tab==='dashboard'} onClick={setTab} />
          <TabButton id="builder" label="Bet Builder" icon={Dice5} active={tab==='builder'} onClick={setTab} />
          <TabButton id="bets" label="Apuestas" icon={Upload} active={tab==='bets'} onClick={setTab} />
          <TabButton id="bankroll" label="Banca" icon={Wallet} active={tab==='bankroll'} onClick={setTab} />
          <TabButton id="import" label="Importar/Exportar" icon={Upload} active={tab==='import'} onClick={setTab} />
          <TabButton id="about" label="Acerca de" icon={Settings} active={tab==='about'} onClick={setTab} />
        </nav>
      </header>

      {/* Main */}
      <main className="max-w-6xl mx-auto px-4 py-6 space-y-8">
        {/* Dashboard */}
        {tab==='dashboard' && (
          <>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="rounded-2xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">Banca actual</p><p className="text-2xl font-semibold">{fmtCurrency(currentBalance, currency)}</p></div>
              <div className="rounded-2xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">Apuestas abiertas</p><p className="text-2xl font-semibold">{openCount}</p></div>
              <div className="rounded-2xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">ROI histórico</p><p className="text-2xl font-semibold">{(roi>=0?'+':'')+roi.toFixed(2)}%</p></div>
            </div>
            <Section title="Actividad reciente">
              <ul className="space-y-2 text-sm text-slate-700">
                {load(LS_KEYS.activity, []).map(a => <li key={a.ts}>{new Date(a.ts).toLocaleString()} • {a.msg}</li>)}
              </ul>
            </Section>
          </>
        )}

        {/* Builder */}
        {tab==='builder' && (
          <Section title="Bet Builder">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500">Deporte</label>
                    <select value={f.sport} onChange={e=>setF({...f, sport:e.target.value})} className="w-full border rounded-lg px-3 py-2">
                      <option>NFL</option><option>NHL</option><option>NBA</option><option>Fútbol</option><option>Tenis</option><option>Otro</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Liga</label>
                    <input value={f.league} onChange={e=>setF({...f, league:e.target.value})} className="w-full border rounded-lg px-3 py-2" placeholder="Ej: Week 7 / Premier / ATP 500" />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Evento</label>
                  <input value={f.event} onChange={e=>setF({...f, event:e.target.value})} className="w-full border rounded-lg px-3 py-2" placeholder="Local vs Visita / Jugador vs Jugador" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500">Mercado</label>
                    <select value={f.market} onChange={e=>setF({...f, market:e.target.value})} className="w-full border rounded-lg px-3 py-2">
                      <option>Moneyline</option><option>Spread</option><option>Total</option><option>Jugador - Prop</option><option>Custom</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Selección</label>
                    <input value={f.selection} onChange={e=>setF({...f, selection:e.target.value})} className="w-full border rounded-lg px-3 py-2" placeholder="Ej: Over 5.5 / DK Metcalf 60+ yds" />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs text-slate-500">Formato cuota</label>
                    <select value={f.legOddsFormat} onChange={e=>setF({...f, legOddsFormat:e.target.value})} className="w-full border rounded-lg px-3 py-2">
                      <option value="american">American (-110)</option>
                      <option value="decimal">Decimal (1.91)</option>
                      <option value="fractional">Fraccional (10/11)</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="text-xs text-slate-500">Cuota</label>
                    <input value={f.odds} onChange={e=>setF({...f, odds:e.target.value})} className="w-full border rounded-lg px-3 py-2" placeholder="-110 / 1.91 / 10/11" />
                  </div>
                </div>
                <button onClick={addLeg} className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 inline-flex items-center gap-2"><Plus size={16}/>Agregar leg</button>
              </div>

              <div className="space-y-4">
                <div className="rounded-xl border p-3">
                  <h3 className="font-medium mb-2">Slip actual</h3>
                  <ul className="text-sm space-y-2">
                    {slip.map((leg,idx) => (
                      <li key={leg.id} className="border rounded-lg p-2 flex items-center justify-between gap-2">
                        <div className="text-sm">
                          <div className="font-medium">{leg.event}</div>
                          <div className="text-xs text-slate-500">{leg.sport} • {leg.league} • {leg.market} • {leg.selection}</div>
                          <div className="text-xs">Cuota: {leg.oddsLabel}</div>
                        </div>
                        <button onClick={()=> setSlip(s => s.filter((_,i)=> i!==idx))} className="px-2 py-1 text-xs rounded-lg border inline-flex items-center gap-1"><Trash2 size={14}/>Quitar</button>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center justify-between mt-3 text-sm">
                    <span>Cuota combinada</span>
                    <span className="font-semibold">{combinedLabel}</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500">Stake</label>
                    <input value={stake} onChange={e=>setStake(e.target.value)} type="number" min="0" step="1" className="w-full border rounded-lg px-3 py-2" placeholder="10000" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Retorno estimado</label>
                    <div className="h-10 grid place-items-center border rounded-lg text-sm">{payout? fmtCurrency(payout, currency): '—'}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={saveBet} className="px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 inline-flex items-center gap-2"><Check size={16}/>Guardar apuesta</button>
                  <button onClick={clearSlip} className="px-4 py-2 rounded-lg border inline-flex items-center gap-2"><X size={16}/>Limpiar slip</button>
                </div>
              </div>
            </div>
          </Section>
        )}

        {/* Bets */}
        {tab==='bets' && (
          <Section title="Apuestas" right={
            <div className="flex gap-2">
              <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
                <option value="ALL">Todas</option><option value="OPEN">Abiertas</option><option value="WON">Ganadas</option><option value="LOST">Perdidas</option><option value="VOID">Void</option>
              </select>
              <input value={query} onChange={e=>setQuery(e.target.value)} className="border rounded-lg px-3 py-2 text-sm" placeholder="Buscar…" />
            </div>
          }>
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-slate-500">
                  <tr>
                    <th className="py-2 pr-3">Fecha</th>
                    <th className="py-2 pr-3">Detalle</th>
                    <th className="py-2 pr-3">Stake</th>
                    <th className="py-2 pr-3">Cuota</th>
                    <th className="py-2 pr-3">Retorno</th>
                    <th className="py-2 pr-3">Estado</th>
                    <th className="py-2">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {bets.filter(b=>{
                    const okStatus = (statusFilter==='ALL') || (b.status===statusFilter)
                    const text = (b.legs.map(l => [l.event, l.market, l.selection].join(' ')).join(' | ') + ' ' + (b.note || '')).toLowerCase()
                    const okQ = !query || text.includes(query.toLowerCase())
                    return okStatus && okQ
                  }).map(b => (
                    <tr key={b.id} className="border-t align-top">
                      <td className="py-2 pr-3 whitespace-nowrap">{new Date(b.ts).toLocaleString()}</td>
                      <td className="py-2 pr-3" dangerouslySetInnerHTML={{__html: b.legs.map(l => `${l.event} • ${l.market} • ${l.selection}`).join('<br/>')}} />
                      <td className="py-2 pr-3 whitespace-nowrap">{fmtCurrency(b.stake, currency)}</td>
                      <td className="py-2 pr-3">{b.oddsDec.toFixed(2)}</td>
                      <td className="py-2 pr-3 whitespace-nowrap">{fmtCurrency(b.payout, currency)}</td>
                      <td className="py-2 pr-3">
                        <span className={`inline-flex items-center px-2 py-1 text-xs rounded-lg border ${
                          b.status==='OPEN' ? '' : b.status==='WON' ? 'bg-emerald-50 border-emerald-300' : b.status==='VOID' ? 'bg-amber-50 border-amber-300' : 'bg-rose-50 border-rose-300'
                        }`}>{b.status}</span>
                      </td>
                      <td className="py-2 whitespace-nowrap">
                        <div className="flex gap-2">
                          <button onClick={()=>settle(b.id,'WON')} className="px-2 py-1 text-xs rounded-lg border">Win</button>
                          <button onClick={()=>settle(b.id,'LOST')} className="px-2 py-1 text-xs rounded-lg border">Loss</button>
                          <button onClick={()=>settle(b.id,'VOID')} className="px-2 py-1 text-xs rounded-lg border">Void</button>
                          <button onClick={()=>delBet(b.id)} className="px-2 py-1 text-xs rounded-lg border">Borrar</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}

        {/* Bankroll */}
        {tab==='bankroll' && (
          <Section title="Banca">
            <div className="grid md:grid-cols-3 gap-3">
              <div className="space-y-2">
                <label className="text-xs text-slate-500">Saldo inicial</label>
                <input value={starting} onChange={e=>setStarting(Number(e.target.value||0))} type="number" className="w-full border rounded-lg px-3 py-2" placeholder="0" />
              </div>
              <BankMovement onAdd={(amt)=>{
                const n = Number(amt||0); if(!n) return
                addLedger(n, n>0?'Depósito':'Retiro', '')
              }}/>
              <div className="space-y-2">
                <label className="text-xs text-slate-500">Saldo actual</label>
                <div className="h-10 grid place-items-center border rounded-lg">{fmtCurrency(currentBalance, currency)}</div>
              </div>
            </div>
            <div className="overflow-auto mt-4">
              <table className="w-full text-sm">
                <thead className="text-left text-slate-500">
                  <tr><th className="py-2 pr-3">Fecha</th><th className="py-2 pr-3">Tipo</th><th className="py-2 pr-3">Monto</th><th className="py-2 pr-3">Nota</th></tr>
                </thead>
                <tbody>
                  {ledger.map(r => (
                    <tr key={r.id} className="border-t">
                      <td className="py-2 pr-3 whitespace-nowrap">{new Date(r.ts).toLocaleString()}</td>
                      <td className="py-2 pr-3">{r.type}</td>
                      <td className="py-2 pr-3 whitespace-nowrap">{fmtCurrency(r.amount, currency)}</td>
                      <td className="py-2 pr-3">{r.note || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}

        {/* Import / Export */}
        {tab==='import' && (
          <Section title="Importar / Exportar">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h3 className="font-medium">Exportar</h3>
                <div className="flex gap-2 flex-wrap">
                  <button onClick={exportJSON} className="px-3 py-2 rounded-lg border">Exportar JSON</button>
                  <button onClick={exportCSV} className="px-3 py-2 rounded-lg border">Exportar CSV</button>
                  <button onClick={exportXLSX} className="px-3 py-2 rounded-lg border">Exportar XLSX</button>
                </div>
              </div>
              <div className="space-y-2">
                <h3 className="font-medium">Importar</h3>
                <input onChange={e=>onImport(e.target.files?.[0])} type="file" className="border rounded-lg px-3 py-2 w-full" accept=".json,.csv,.xlsx" />
                <p className="text-xs text-slate-500">Acepta JSON / CSV / XLSX (hojas: Bets, Ledger, Settings)</p>
              </div>
            </div>
          </Section>
        )}

        {/* About */}
        {tab==='about' && (
          <Section title="Acerca de BeatBetano">
            <div className="space-y-3">
              <p className="text-sm text-slate-700">Starter en React + Vite para gestionar apuestas. Los datos se guardan en tu navegador.</p>
              <ul className="text-sm list-disc pl-5 text-slate-700">
                <li>Cuotas American / Decimal / Fraccional</li>
                <li>Parlays con cálculo automático</li>
                <li>Export/Import JSON/CSV/XLSX</li>
                <li>ROI y estado de apuestas</li>
              </ul>
              <p className="text-xs text-slate-500">Versión {VERSION}</p>
            </div>
          </Section>
        )}
      </main>
    </div>
  )
}

function BankMovement({ onAdd }){
  const [n, setN] = useState('')
  return (
    <div className="space-y-2">
      <label className="text-xs text-slate-500">Movimiento (+ depósito / - retiro)</label>
      <div className="flex gap-2">
        <input value={n} onChange={e=>setN(e.target.value)} type="number" className="w-full border rounded-lg px-3 py-2" placeholder="100000" />
        <button onClick={()=>{ const v = Number(n||0); if(!v) return; onAdd(v); setN('') }} className="px-4 py-2 rounded-lg bg-indigo-600 text-white">Agregar</button>
      </div>
    </div>
  )
}
