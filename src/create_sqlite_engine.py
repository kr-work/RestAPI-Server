import pathlib

from sqlalchemy.ext.asyncio import create_async_engine

file_path = pathlib.Path(__file__).parents[1]
file_path /= "./src/basic_certification.sqlite3"
sqlite_url = f"sqlite+aiosqlite:///{file_path}"


engine = create_async_engine(url=sqlite_url, echo=False)