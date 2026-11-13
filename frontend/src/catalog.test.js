import test from 'node:test'
import assert from 'node:assert/strict'
import { eventParams, priceLabel, webUrl } from './catalog.js'

test('calendar filters use UTC+5 and preserve a zero budget', () => {
  const params = eventParams({ date: '2026-11-14', price_max: '0', city_id: 'city' }, 9, new Date('2026-11-13T12:00Z'))
  assert.equal(params.get('date_from'), '2026-11-13T19:00:00.000Z')
  assert.equal(params.get('date_to'), '2026-11-14T18:59:59.999Z')
  assert.equal(params.get('price_max'), '0')
  assert.equal(params.get('offset'), '9')
})

test('empty filters are omitted and past events excluded', () => {
  const params = eventParams({ q: '', category_id: '' }, 0, new Date('2026-11-13T12:00Z'))
  assert.equal(params.has('q'), false)
  assert.equal(params.get('date_from'), '2026-11-13T12:00:00.000Z')
})

test('unknown, free and paid prices have different labels', () => {
  assert.equal(priceLabel({}), 'Цена уточняется')
  assert.equal(priceLabel({ price_min: 0 }), 'Бесплатно')
  assert.equal(priceLabel({ price_min: 500 }), 'от 500 ₽')
})

test('links reject unsafe schemes and resolve relative poster paths', () => {
  assert.equal(webUrl('javascript:alert(1)'), undefined)
  assert.equal(webUrl('/poster.jpg'), 'https://ufa.burocultura.ru/poster.jpg')
})
