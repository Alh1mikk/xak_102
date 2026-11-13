import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { eventParams, priceLabel, webUrl } from './catalog.js'
import '../style.css'
import EventMap from './Map.jsx'
import Account from './Account.jsx'

const initialFilters = { city_id: '', category_id: '', date: '', price_max: '', q: '' }
const dateFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Yekaterinburg',
})

async function api(path, options) {
  const response = await fetch('/api' + path, options)
  if (!response.ok) throw new Error('Не удалось получить данные. Попробуйте ещё раз.')
  return response.json()
}

function Poster({ event }) {
  const source = webUrl(event.source_urls?.[0])
  const image = webUrl(event.image_url)
  return <article className="poster">
    <div className="art">
      {image && <img src={image} alt="" loading="lazy" onError={e => { e.currentTarget.hidden = true }} />}
      <span className="date">{dateFormat.format(new Date(event.start_at))}</span>
    </div>
    <div className="poster-info">
      <p className="poster-meta">{[event.category?.name, event.city?.name, event.age_limit == null ? null : event.age_limit + '+'].filter(Boolean).join(' / ')}</p>
      <h3>{event.title}</h3>
      {event.address && <p>{event.address}</p>}
      <div className="poster-bottom"><strong>{priceLabel(event)}</strong>{source && <a href={source} target="_blank" rel="noreferrer" aria-label={'Открыть источник: ' + event.title}>↗</a>}</div>
    </div>
  </article>
}

function orderedStops(events) {
  return [...events].sort((first, second) => Date.parse(first.start_at) - Date.parse(second.start_at))
}

function App() {
  const [filters, setFilters] = useState(initialFilters)
  const [reference, setReference] = useState({ cities: [], categories: [] })
  const [offset, setOffset] = useState(0)
  const [catalog, setCatalog] = useState({ events: [], loading: true, more: false, error: '' })
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [user, setUser] = useState(null)
  const [selected, setSelected] = useState([])
  const [route, setRoute] = useState(null)
  const [routing, setRouting] = useState(false)
  const [routeError, setRouteError] = useState('')
  const [page, setPage] = useState(() => location.hash.slice(1) || 'events')
  useEffect(() => {
    const onHash = () => { setPage(location.hash.slice(1) || 'events'); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', onHash)
    api('/auth/me').then(setUser).catch(() => {})
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const options = { signal: controller.signal }
    Promise.all([api('/events/cities', options), api('/events/categories', options)])
      .then(([cities, categories]) => setReference({ cities, categories }))
      .catch(() => {})
    return () => controller.abort()
  }, [retry])

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const events = await api('/events/?' + eventParams(filters, offset), { signal: controller.signal })
        setCatalog(current => ({ events: offset ? [...current.events, ...events] : events, loading: false, more: events.length === 9, error: '' }))
      } catch (error) {
        if (!controller.signal.aborted) setCatalog(current => ({ ...current, loading: false, error: error.message }))
      }
    }, 150)
    return () => { clearTimeout(timer); controller.abort() }
  }, [filters, offset, retry])

  function updateFilters(next) {
    setCatalog({ events: [], loading: true, more: false, error: '' })
    setOffset(0)
    setFilters(next)
  }

  async function search(event) {
    event.preventDefault()
    if (!query.trim() || searching) return
    setSearching(true)
    const text = query.trim()
    setQuery('')
    setMessages(current => [...current, { text }])
    setSearchError('')
    try {
      const previous = messages.filter(message => message.text).map(message => message.text).join(' ').slice(0, 500)
      const reply = await api('/ai/search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, previous_text: previous }),
      })
      setMessages(current => [...current, { reply }])
    } catch (error) {
      setSearchError(error.message)
    } finally {
      setSearching(false)
    }
  }

  async function buildRoute() {
    setRouting(true)
    setRouteError('')
    try {
      const points = orderedStops(selected).map(event => [event.longitude, event.latitude].join(','))
      const unique = points.filter((point, index) => index === 0 || point !== points[index - 1])
      if (unique.length < 2) {
        setRouteError('Все выбранные события на одной площадке.')
        return
      }
      const response = await fetch('https://routing.openstreetmap.de/routed-foot/route/v1/driving/' + unique.join(';') + '?overview=full&geometries=geojson', { signal: AbortSignal.timeout(15000) })
      if (!response.ok) throw new Error()
      const result = await response.json()
      if (!result.routes?.[0]) throw new Error()
      setRoute(result.routes[0])
    } catch {
      setRouteError('Пешеходный маршрут сейчас недоступен. На карте видны выбранные площадки.')
    } finally {
      setRouting(false)
    }
  }

  return <>
    <header className="site-header">
      <nav className="wrap" aria-label="Главное меню">
        <a className="brand" href="#events"><span className="brand-dot" />Вне афиши</a>
        <div className="tabs">
          {[['events', 'События'], ['chat', 'ИИ-подборка'], ['account', user ? 'Профиль' : 'Войти']].map(([key, label]) =>
            <a key={key} href={'#' + key} aria-current={page === key ? 'page' : undefined}>{label}</a>)}
        </div>
      </nav>
    </header>
    <main>
      {page === 'chat' && <section className="wrap page chat">
        <h1>ИИ-подборка</h1>
        {messages.length === 0 && <p>Расскажите, куда хочется сходить и с кем.</p>}
        <div className="chat-log" aria-live="polite">
          {messages.map((message, index) => message.text
            ? <p className="bubble mine" key={index}>{message.text}</p>
            : <div className="bubble" key={index}>
                <p>{message.reply.explanation}</p>
                <div className="chat-cards">{message.reply.events.map(event => <div className="choice" key={event.id}>
                  <Poster event={event} />
                  {event.latitude != null && <button className="route-choice" aria-pressed={selected.some(item => item.id === event.id)} disabled={routing} onClick={() => {
                    setRoute(null)
                    setRouteError('')
                    setSelected(current => current.some(item => item.id === event.id) ? current.filter(item => item.id !== event.id) : [...current, event])
                  }}>{selected.some(item => item.id === event.id) ? 'Убрать из маршрута' : 'В маршрут +'}</button>}
                </div>)}</div>
              </div>)}
          {searching && <p role="status">Подбираем события…</p>}
          {searchError && <p role="alert">{searchError}</p>}
        </div>
        <form className="search" onSubmit={search}>
          <label htmlFor="query">Ваш запрос</label>
          <div className="search-line">
            <input id="query" value={query} maxLength={500} required onChange={e => setQuery(e.target.value)} placeholder="Куда сходить с ребёнком?" />
            <button className="primary" disabled={searching} type="submit">Отправить</button>
          </div>
        </form>
        {!!messages.length && <button className="reset-chat" disabled={searching || routing} onClick={() => { setMessages([]); setSearchError(''); setSelected([]); setRoute(null); setRouteError('') }}>Начать новый диалог</button>}
        {selected.length > 0 && <section className="route-panel">
          <h2>Мой маршрут</h2>
          <ol>{orderedStops(selected).map(event => <li key={event.id}>{dateFormat.format(new Date(event.start_at))} · {event.title}</li>)}</ol>
          <button className="primary" disabled={routing || selected.length < 2 || selected.length > 10} onClick={buildRoute}>{routing ? 'Строим маршрут…' : 'Построить пеший маршрут'}</button>
          {selected.length < 2 && <p>Выберите ещё одно событие.</p>}
          {selected.length > 10 && <p>Выберите до десяти событий.</p>}
          {routeError && <p role="status">{routeError}</p>}
          {route && <p>{(route.distance / 1000).toFixed(1)} км · {Math.ceil(route.duration / 60)} мин пешком</p>}
          <EventMap events={orderedStops(selected)} route={route} />
        </section>}
      </section>}
      {page === 'account' && <Account api={api} user={user} setUser={setUser} />}
      {!['chat', 'account'].includes(page) && <section className="catalog page" id="catalog">
        <div className="wrap">
          <div className="catalog-head"><div><p className="location">Башкортостан</p><h1>События</h1></div></div>
          <aside className="project-intro">
            <div><h2>Культура рядом</h2><p>«Вне афиши» собирает спектакли, выставки и концерты Башкортостана. Найдите, куда сходить с семьёй, друзьями или самостоятельно.</p></div>
            <a className="primary" href="#chat">Подобрать событие ↗</a>
          </aside>
          <form className="filters" onSubmit={e => e.preventDefault()}>
            <label>Город<select value={filters.city_id} onChange={e => updateFilters({ ...filters, city_id: e.target.value })}>
              <option value="">Все города</option>{reference.cities.map(city => <option key={city.id} value={city.id}>{city.name}</option>)}
            </select></label>
            <label>Категория<select value={filters.category_id} onChange={e => updateFilters({ ...filters, category_id: e.target.value })}>
              <option value="">Все категории</option>{reference.categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select></label>
            <label>Дата<input type="date" value={filters.date} onChange={e => updateFilters({ ...filters, date: e.target.value })} /></label>
            <label>Цена до, ₽<input type="number" min="0" step="1" placeholder="Любая" value={filters.price_max} onChange={e => updateFilters({ ...filters, price_max: e.target.value })} /></label>
            <label>Название<input type="search" placeholder="Найти событие" value={filters.q} onChange={e => updateFilters({ ...filters, q: e.target.value })} /></label>
            <button type="button" onClick={() => updateFilters({ ...initialFilters })}>Сбросить</button>
          </form>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">{catalog.events.map(event => <Poster key={event.id} event={event} />)}</div>
          {catalog.loading && <p role="status" className="status">Загружаем события…</p>}
          {catalog.error && <p role="alert" className="status">{catalog.error} <button onClick={() => setRetry(value => value + 1)}>Повторить</button></p>}
          {!catalog.loading && !catalog.error && !catalog.events.length && <p role="status" className="status">Событий по этим фильтрам пока нет.</p>}
          {catalog.more && !catalog.loading && !catalog.error && <button className="load" onClick={() => { setCatalog({ ...catalog, loading: true }); setOffset(value => value + 9) }}>Ещё события ↓</button>}
        </div>
      </section>}
    </main>
    <footer><div className="wrap">Вне афиши</div></footer>
  </>
}

createRoot(document.getElementById('root')).render(<App />)
