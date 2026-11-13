import requests
from datetime import datetime
from app.schemas import EventCreate
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

def parse_burocultura():
    url = "https://ufa.burocultura.ru/api/events"
    response = requests.get(url)
    response.raise_for_status()
    events_data = response.json() # Это список словарей

    normalized_events = []
    for item in events_data:
        # Приводим к единому формату
        event = {
            "title": item.get("title"),
            "description": item.get("description"),
            "category": item.get("type"),  # 'concert', 'theater' и т.д
            "date_start": item.get("dateStart"), # Уже в ISO формате '2026-11-13T14:00:00.000Z'
            "price_min": item.get("priceFrom"),
            "age_restriction": item.get("ageRestriction"),
            "image_url": item.get("imageUrl"),
            "source_url": f"https://ufa.burocultura.ru/events/{item.get('slug')}",
            "source_site": "burocultura.ru",
        }
        normalized_events.append(event)
    
    return normalized_events

def parse_kulturarb():
    url = "https://kulturarb.ru/ru/afisha"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    event_items = soup.find_all('div', class_='event-item')

    normalized_events = []
    for item in event_items:
        title_tag = item.find('h3') # или другой тег
        date_tag = item.find('span', class_='date')
        
        title = title_tag.text.strip() if title_tag else None
        date_str = date_tag.text.strip() if date_tag else None
        
        event = {
            "title": title,
            "date_start": date_parser.parse(date_str, fuzzy=True) if date_str else None,
            "source_url": url,
            "source_site": "kulturarb.ru",
        }
        normalized_events.append(event)

    return normalized_events

def main():
    print("Парсим burocultura...")
    buro_events = parse_burocultura()
    
    print("Парсим kulturarb...")
    kultura_events = parse_kulturarb()
    
    all_events = buro_events + kultura_events
    
    print(f"Всего собрано событий: {len(all_events)}")