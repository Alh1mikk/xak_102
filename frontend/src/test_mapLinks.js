import test from 'node:test'
import assert from 'node:assert/strict'
import { mapLinks } from './mapLinks.js'

test('returns empty when fewer than 2 events', () => {
  assert.deepEqual(mapLinks([]), [])
  assert.deepEqual(mapLinks([{ latitude: 1, longitude: 2 }]), [])
})

test('keeps only unique coordinates', () => {
  const links = mapLinks([
    { latitude: 1, longitude: 2 },
    { latitude: 1, longitude: 2 },
    { latitude: 3, longitude: 4 },
  ])
  assert.equal(links.length, 1)
  assert.match(links[0].url, /rtext=1%2C2~3%2C4/)
})

test('builds yandex and apple links', () => {
  const links = mapLinks([
    { latitude: 54.7, longitude: 55.9 },
    { latitude: 54.8, longitude: 56.0 },
    { latitude: 54.9, longitude: 56.1 },
  ])
  assert.equal(links[0].name, 'Яндекс Карты')
  assert.match(links[0].url, /^https:\/\/yandex\.ru\/maps\/\?rtext=/)
  assert.equal(links[links.length - 1].name, 'Apple Maps')
})

test('builds google links with waypoints for more than 2 points', () => {
  const links = mapLinks([
    { latitude: 1, longitude: 1 },
    { latitude: 2, longitude: 2 },
    { latitude: 3, longitude: 3 },
    { latitude: 4, longitude: 4 },
    { latitude: 5, longitude: 5 },
  ])
  const google = links.find(l => l.name.startsWith('Google Maps'))
  assert.ok(google)
  const params = new URLSearchParams(google.url.split('?')[1])
  assert.equal(params.get('origin'), '1,1')
  assert.equal(params.get('destination'), '5,5')
  assert.equal(params.get('waypoints'), '2,2|3,3|4,4')
})

test('splits google links when more than 5 points', () => {
  const events = Array.from({ length: 10 }, (_, i) => ({ latitude: i, longitude: i }))
  const links = mapLinks(events)
  const googleNames = links.filter(l => l.name.startsWith('Google Maps')).map(l => l.name)
  assert.ok(googleNames.length > 1)
  const firstGoogle = links.find(l => l.name === googleNames[0])
  const lastGoogle = links.find(l => l.name === googleNames[googleNames.length - 1])
  assert.equal(firstGoogle.url, lastGoogle.url)
})

test('rejects unsafe schemes', () => {
  assert.equal(mapLinks([{ latitude: 1, longitude: 2 }]), undefined)
})
