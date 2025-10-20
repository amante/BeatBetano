import React from 'react'
export default function EnvCheck(){
  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <div className="rounded-2xl bg-white p-6 shadow-sm space-y-2">
        <h2 className="font-semibold text-lg">Comprobación de entorno</h2>
        <p className="text-sm text-slate-600">BASE_URL (según Vite):</p>
        <pre className="text-xs p-3 bg-slate-50 rounded-lg border">{String(import.meta.env.BASE_URL)}</pre>
        <p className="text-sm text-slate-600">Debería ser: <code>/BeatBetano/</code> si el repo tiene B mayúscula.</p>
      </div>
    </main>
  )
}
