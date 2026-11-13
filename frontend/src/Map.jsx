import React, { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { webUrl } from './catalog.js'

export default function EventMap({ events, route }) {
  const element = useRef(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const map = L.map(element.current, { scrollWheelZoom: false }).setView([54.73, 55.96], 12)
    map.attributionControl.setPrefix(false)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).on('tileerror', () => setFailed(true)).addTo(map)
    const venues = new Map()
    for (const event of events) {
      if (event.latitude == null || event.longitude == null) continue
      const key = [event.latitude, event.longitude].join(',')
      if (!venues.has(key)) venues.set(key, { point: [event.latitude, event.longitude], events: [] })
      venues.get(key).events.push(event)
    }
    const bounds = []
    for (const venue of venues.values()) {
      const popup = document.createElement('div')
      for (const event of venue.events) {
        const row = document.createElement('p')
        const link = webUrl(event.source_urls?.[0])
        const title = document.createElement(link ? 'a' : 'span')
        title.textContent = event.title
        if (link) {
          title.href = link
          title.target = '_blank'
          title.rel = 'noreferrer'
        }
        row.append(title)
        popup.append(row)
      }
      L.marker(venue.point, {
        icon: L.divIcon({ className: 'venue-marker', html: String(venue.events.length), iconSize: [34, 34] }),
        title: venue.events[0].address || venue.events[0].title,
      }).bindPopup(popup, { maxHeight: 200 }).addTo(map)
      bounds.push(venue.point)
    }
    if (route) L.geoJSON(route.geometry, { style: { color: "#245741", weight: 5 } }).addTo(map)
    if (bounds.length) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 14 })
    return () => map.remove()
  }, [events, route])
  return <><div className="event-map" ref={element} aria-label="Карта событий" />{route && <a className="map-credit" href="https://routing.openstreetmap.de/">Маршрут © FOSSGIS / OSRM</a>}{failed && <p>Подложка карты сейчас недоступна. Выбранные точки остаются на карте.</p>}</>
}
