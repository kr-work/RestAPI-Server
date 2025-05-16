from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from uuid import uuid4

from src.authentication.basic_authentication import BasicAuthentication
from src.crud import CreateData
from src.routers import match
from src.routers.match import Session
from src.routers import restapi
from src.models.schema_models import PlayerSchema, PhysicalSimulatorSchema
from src.load_secrets import db_name, host, password, port, user

POSTGRES_DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

basic_auth = BasicAuthentication()
scheduler = AsyncIOScheduler()
logging.basicConfig(level=logging.DEBUG)

# notification_queue = asyncio.Queue()
create_data = CreateData()


@asynccontextmanager
async def lifespan(app):
    """Create default player data to use learning AI.
    This function is called to start the server.
    """
    first_player = PlayerSchema(
        player_id="006951d4-37b2-48eb-85a2-af9463a1e7aa",
        team_id="5050f20f-cf97-4fb1-bbc1-f2c9052e0d17",
        max_velocity=4.0,
        shot_dispersion_rate=0.1,
        player_name="first",
    )
    second_player = PlayerSchema(
        player_id="0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",
        team_id="60e1e056-3613-4846-afc9-514ea7b6adde",
        max_velocity=4.0,
        shot_dispersion_rate=0.1,
        player_name="second",
    )
    simulator = PhysicalSimulatorSchema(
        physical_simulator_id=uuid4(), simulator_name="fcv1"
    )
    async with Session() as session:
        await create_data.create_default_player_data(first_player, session)
        await create_data.create_default_player_data(second_player, session)
        await create_data.create_physical_simulator_data(simulator, session)

    # If the match data is expired, delete the match data
    scheduler.add_job(
        basic_auth.delete_expired_match_data,
        "interval",
        hours=24,
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()
        logging.info("Stop Server")


# loop = asyncio.get_event_loop()
# loop.create_task(cd.create_table())

app = FastAPI(lifespan=lifespan)
# app.add_middleware(HTTPSRedirectMiddleware)
app.include_router(match.match_router)
app.include_router(restapi.rest_router)


# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
