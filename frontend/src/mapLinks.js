export function mapLinks(events) {
  const points = events.filter(event => Number.isFinite(event.latitude) && Number.isFinite(event.longitude))
    .map(event => [event.latitude, event.longitude].join(','))
    .filter((point, index, all) => point !== all[index - 1])
  if (points.length < 2) return []
  const yandex = new URL('https://yandex.ru/maps/')
  yandex.search = new URLSearchParams({ rtext: points.join('~'), rtt: 'pd' })
  const apple = new URL('https://maps.apple.com/directions')
  apple.search = new URLSearchParams({ source: points[0], destination: points.at(-1), mode: 'walking' })
  for (const point of points.slice(1, -1)) apple.searchParams.append('waypoint', point)
  const links = [{ name: 'Яндекс Карты', url: yandex.href }]
  const split = points.length > 5
  for (let start = 0; start < points.length - 1; start += 4) {
    const leg = points.slice(start, start + 5)
    const google = new URL('https://www.google.com/maps/dir/')
    google.search = new URLSearchParams({ api: '1', origin: leg[0], destination: leg.at(-1), travelmode: 'walking' })
    if (leg.length > 2) google.searchParams.set('waypoints', leg.slice(1, -1).join('|'))
    links.push({ name: split ? 'Google Maps · ' + (start / 4 + 1) : 'Google Maps', url: google.href })
  }
  return [...links, { name: 'Apple Maps', url: apple.href }]
}
