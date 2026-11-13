import React, { useEffect, useState } from 'react'

export default function Preferences({ api, reference }) {
  const [prefs, setPrefs] = useState(null)
  const [link, setLink] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const load = () => api('/preferences').then(setPrefs).catch(e => setError(e.message))
  useEffect(() => { load() }, [])
  async function save(event) {
    event.preventDefault()
    setStatus('')
    setError('')
    try {
      await api('/preferences', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(prefs) })
      setStatus('Предпочтения сохранены')
    } catch (e) { setError(e.message) }
  }
  return <section className="preferences">
    <h2>Предпочтения</h2>
    {prefs && <form className="search" onSubmit={save}>
      <label>Город<select value={prefs.city_id || ''} onChange={e => setPrefs({ ...prefs, city_id: e.target.value || null })}>
        <option value="">Все города</option>{reference.cities.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      <label>Категория<select value={prefs.category_id || ''} onChange={e => setPrefs({ ...prefs, category_id: e.target.value || null })}>
        <option value="">Все категории</option>{reference.categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      <label>Бюджет на билет, ₽<input type="number" min="0" max="1000000" value={prefs.price_max ?? ''} onChange={e => setPrefs({ ...prefs, price_max: e.target.value === '' ? null : Number(e.target.value) })} /></label>
      <label className="check"><input type="checkbox" checked={!!prefs.family_only} onChange={e => setPrefs({ ...prefs, family_only: e.target.checked })} /> Детские и школьные события</label>
      <label className="check"><input type="checkbox" checked={prefs.weekly} onChange={e => setPrefs({ ...prefs, weekly: e.target.checked })} /> Подборка в Telegram по четвергам</label>
      <button className="primary">Сохранить</button>
    </form>}
    <div className="profile-actions">
      {prefs?.linked ? <button onClick={async () => {
        try { await api('/preferences/telegram', { method: 'DELETE' }); setLink(''); await load() }
        catch (e) { setError(e.message) }
      }}>Отвязать Telegram</button> : <button onClick={async () => {
        try { setError(''); setLink((await api('/preferences/telegram', { method: 'POST' })).url) }
        catch (e) { setError(e.message) }
      }}>Привязать Telegram</button>}
      {link && <><a href={link} target="_blank" rel="noreferrer">Открыть бота и нажать Start ↗</a><button onClick={load}>Проверить привязку</button></>}
    </div>
    {status && <p role="status">{status}</p>}
    {error && <p role="alert">{error}</p>}
  </section>
}
