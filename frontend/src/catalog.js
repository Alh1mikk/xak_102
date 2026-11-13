export function eventParams(filters, offset = 0, now = new Date()) {
  const params = new URLSearchParams({ limit: '9', offset: String(offset) })
  const start = filters.date ? new Date(filters.date + 'T00:00:00+05:00') : now
  params.set('date_from', new Date(Math.max(+now, +start)).toISOString())
  if (filters.date) params.set('date_to', new Date(filters.date + 'T23:59:59.999+05:00').toISOString())
  for (const key of ['city_id', 'category_id', 'price_max', 'q']) {
    if (filters[key] !== '' && filters[key] != null) params.set(key, filters[key])
  }
  return params
}

export function priceLabel(event) {
  if (event.price_min == null) return 'Цена уточняется'
  if (event.price_min === 0 && !event.price_max) return 'Бесплатно'
  return `от ${event.price_min.toLocaleString('ru-RU')} ₽`
}

export function webUrl(value) {
  try {
    const url = new URL(value, 'https://ufa.burocultura.ru/')
    return value && ['https:', 'http:'].includes(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}
