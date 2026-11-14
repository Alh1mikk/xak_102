import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine

url = os.getenv('DATABASE_URL')
print('DATABASE_URL:', url)

if url:
    engine = create_async_engine(url, echo=False)
    print('Engine created successfully')
else:
    print('URL is None')