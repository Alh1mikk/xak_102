import React, { useEffect, useState } from 'react'
import Preferences from './Preferences.jsx'

export default function Account({ api, user, setUser, reference }) {
  const [email, setEmail] = useState('')
  const [enabled, setEnabled] = useState(null)
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [code, setCode] = useState('')

  useEffect(() => {
    api('/auth/config').then(config => setEnabled(config.email_enabled)).catch(() => setEnabled(false))
  }, [])

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await api(sent ? '/auth/email/confirm' : '/auth/email/request', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sent ? { email, code } : { email }),
      })
      if (sent) {
        setSent(false)
        setCode('')
        setUser(response)
      } else setSent(true)
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <section className="wrap page"><div className="account-panel">
    <h1 className="page-reveal">{user && !sent ? 'Профиль' : 'Вход'} <span className="page-star" aria-hidden="true">✦</span></h1>
    {user && !sent ? <><p>{user.name}</p><button className="primary" onClick={async () => {
      try { await api('/auth/logout', { method: 'POST' }); setUser(null) } catch (error) { setError(error.message) }
    }}>Выйти</button><Preferences api={api} reference={reference} /></> : <form className="search" onSubmit={submit}>
      {sent ? <><p>Код отправлен на {email}. Он действует 15 минут.</p>
        <label htmlFor="code">Код из письма</label><input id="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={e => setCode(e.target.value)} />
        <button type="button" onClick={() => { setSent(false); setCode(''); setError('') }}>Другой адрес или новый код</button></> : <>
        <p>Пришлём шестизначный код для входа.</p>
        <label htmlFor="email">Почта</label>
        <input id="email" type="email" autoComplete="email" maxLength={254} required value={email} onChange={e => { setEmail(e.target.value); setSent(false) }} />
      </>}
      <button className="primary" disabled={busy || (!sent && !enabled)} type="submit">{sent ? 'Подтвердить вход' : 'Получить код'}</button>
      {enabled === false && !sent && <p role="status">Отправка писем пока не настроена.</p>}

    </form>}
    {error && <p role="alert">{error}</p>}
  </div></section>
}
