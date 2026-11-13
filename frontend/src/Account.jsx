import React, { useEffect, useState } from 'react'

export default function Account({ api, user, setUser }) {
  const [email, setEmail] = useState('')
  const [enabled, setEnabled] = useState(null)
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const params = new URLSearchParams(location.hash.split('?')[1])
  const token = params.get('token')
  const linkedEmail = params.get('email')

  useEffect(() => {
    api('/auth/config').then(config => setEnabled(config.email_enabled)).catch(() => setEnabled(false))
  }, [])

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await api(token ? '/auth/email/confirm' : '/auth/email/request', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(token ? { email: linkedEmail, token } : { email }),
      })
      if (token) {
        history.replaceState(null, '', '#account')
        setUser(response)
      } else setSent(true)
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <section className="wrap page"><div className="account-panel">
    <h1>{user && !token ? 'Профиль' : 'Вход'}</h1>
    {user && !token ? <><p>{user.name}</p><button className="primary" onClick={async () => {
      try { await api('/auth/logout', { method: 'POST' }); setUser(null) } catch (error) { setError(error.message) }
    }}>Выйти</button></> : <form className="search" onSubmit={submit}>
      {token ? <p>Подтвердите вход для {linkedEmail}.</p> : <>
        <p>Пришлём одноразовую ссылку для входа.</p>
        <label htmlFor="email">Почта</label>
        <input id="email" type="email" autoComplete="email" maxLength={254} required value={email} onChange={e => { setEmail(e.target.value); setSent(false) }} />
      </>}
      <button className="primary" disabled={busy || (!token && !enabled)} type="submit">{token ? 'Подтвердить вход' : 'Получить ссылку'}</button>
      {enabled === false && !token && <p role="status">Отправка писем пока не настроена.</p>}
      {sent && <p role="status">Проверьте почту. Ссылка действует 15 минут.</p>}
    </form>}
    {error && <p role="alert">{error}</p>}
  </div></section>
}
