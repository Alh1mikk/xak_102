import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine
from app.main import app

url = os.getenv('DATABASE_URL')
print('DATABASE_URL:', url)

if url:
    engine = create_async_engine(url, echo=False)
    print('Engine created successfully')

print('App title:', app.title)
print('App imported successfully')