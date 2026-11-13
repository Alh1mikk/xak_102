import React, { useEffect, useRef, useState } from 'react'

export default function Account({ api, user, setUser }) {
  const [bot, setBot] = useState(undefined)
  const [error, setError] = useState('')
  const host = useRef(null)
  useEffect(() => { api('/auth/config').then(config => setBot(config.telegram_bot)).catch(() => setBot(null)) }, [])
  useEffect(() => {
    if (!bot || user || !host.current) return
    const element = host.current
    window.onAfishaTelegramAuth = async payload => {
      try {
        setUser(await api('/auth/telegram', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        }))
      } catch (error) {
        setError(error.message)
      }
    }
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.async = true
    script.dataset.telegramLogin = bot
    script.dataset.size = 'large'
    script.dataset.onauth = 'onAfishaTelegramAuth(user)'
    element.append(script)
    return () => { element.replaceChildren(); delete window.onAfishaTelegramAuth }
  }, [bot, user])
  return <section className="wrap page"><div className="account-panel"><h1>{user ? "Профиль" : "Вход"}</h1>
    {user ? <><p>{user.name}</p><button className="primary" onClick={async () => {
      try { await api('/auth/logout', { method: 'POST' }); setUser(null) } catch (error) { setError(error.message) }
    }}>Выйти</button></> : <><p>Используйте аккаунт Telegram для входа в «Вне афиши».</p><div ref={host} />
      {bot === null && <p role="status">В этой локальной версии вход через Telegram ещё не подключён. Каталог и подборки доступны без аккаунта.</p>}</>}
    {error && <p role="alert">{error}</p>}
  </div></section>
}
