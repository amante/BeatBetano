export const VERSION='v1.2.3'
export const LS_KEYS={ bets:'beatbetano_bets', ledger:'beatbetano_ledger', settings:'beatbetano_settings', starting:'beatbetano_starting', activity:'beatbetano_activity', slipDraft:'beatbetano_slip_draft' }
export const save=(k,v)=>localStorage.setItem(k, JSON.stringify(v))
export const load=(k,f)=>JSON.parse(localStorage.getItem(k)||JSON.stringify(f))
export const nowISO=()=>new Date().toISOString()
export const getSettings=()=>load(LS_KEYS.settings,{currency:'CLP',oddsFormat:'american'})
export const setSettings=(p)=>{ const s={...getSettings(),...p}; save(LS_KEYS.settings,s); return s }
export const fmtCurrency=(v,curr)=>{ const map={CLP:'es-CL',USD:'en-US',EUR:'de-DE'}; const currency=curr||getSettings().currency; try{return new Intl.NumberFormat(map[currency]||'es-CL',{style:'currency',currency}).format(Number(v||0))}catch{return currency+' '+Number(v||0).toFixed(2)} }
export const pushActivity=(msg)=>{ const list=load(LS_KEYS.activity,[]); list.unshift({ts:nowISO(),msg}); save(LS_KEYS.activity,list.slice(0,15)) }
export const americanToDecimal=(a)=>{ const n=Number(a); if(!isFinite(n)||n===0) return null; return n>0?1+n/100:1+100/Math.abs(n) }
export const fractionalToDecimal=(fr)=>{ const [num,den]=String(fr).split('/').map(Number); if(!isFinite(num)||!isFinite(den)||den===0) return null; return 1+num/den }
export const toDecimalOdds=(input,fmt)=> fmt==='decimal'?(Number(input)>1?Number(input):null): fmt==='american'?americanToDecimal(input): fmt==='fractional'?fractionalToDecimal(input): null
export const decimalToAmerican=(d)=>{ const x=Number(d); if(!isFinite(x)||x<=1) return null; return x>=2? Math.round((x-1)*100) : -Math.round(100/(x-1)) }
export const toFraction=(dec)=>{ const x=Number(dec); if(!isFinite(x)||x<=1) return '—'; const v=x-1,den=1000; const num=Math.round(v*den); const g=(a,b)=>b?g(b,a%b):a; const m=g(num,den); return `${Math.round(num/m)}/${Math.round(den/m)}` }
export const parlayDecimal=(legs)=> legs.reduce((p,l)=> p*Number(l.oddsDec),1)
export const getDraftSlip=()=>load(LS_KEYS.slipDraft,[])
export const setDraftSlip=(arr)=>save(LS_KEYS.slipDraft,arr)
