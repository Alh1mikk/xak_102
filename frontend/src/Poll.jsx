import React, { useEffect, useState } from 'react'

export default function Poll({ id, api, Poster, onRoute }) {
  const [poll, setPoll] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const path = '/polls/' + encodeURIComponent(id)
  const load = () => api(path).then(setPoll)
  useEffect(() => { load().catch(e => setError(e.message)) }, [id])
  const most = poll ? Math.max(0, ...Object.values(poll.counts)) : 0
  const leaders = poll?.events.filter(event => most && poll.counts[event.id] === most) || []
  return <section className="wrap page">
    <h1>Выбираем вместе</h1>
    <p>Выберите одно событие. Голос можно поменять.</p>
    {error && <p role="alert">{error}</p>}
    {poll && <div className="chat-cards">{poll.events.map(event => <div key={event.id}>
      <Poster event={event} />
      <button className="route-choice" disabled={busy} aria-pressed={poll.vote === event.id} onClick={async () => {
        setBusy(true)
        try {
          await api(path + '/vote', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_id: event.id }) })
          await load()
        } catch (e) { setError(e.message) } finally { setBusy(false) }
      }}>Голосовать · {poll.counts[event.id] || 0}</button>
    </div>)}</div>}
    {leaders.length > 0 && <button className="primary load" onClick={() => onRoute(leaders)}>Добавить лидеров в маршрут</button>}
  </section>
}
