import asyncio
import json
import logging
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.crud import ReadData
from src.models.schema_models import StateSchema, MatchDataSchema
from src.models.dc_models import StateModel
from src.converter import DataConverter

HEART_BEAT = 15

logging.basicConfig(level=logging.INFO)

read_data = ReadData()
data_converter = DataConverter()


class RedisSubscriber:
    def __init__(self, Session: async_sessionmaker, match_id: str):
        self.match_id: str = match_id
        self.Session: async_sessionmaker = Session

    async def event_generator(self, channel: str, redis: Redis):
        pubsub = redis.pubsub()
        event_id = 0

        async with self.Session() as session:
            match_data: MatchDataSchema = await read_data.read_match_data(
                self.match_id, session
            )
            latest_state_data: StateSchema = await read_data.read_latest_state_data(
                self.match_id, session
            )
        latest_state_data: StateModel = (
            data_converter.convert_stateschema_to_statemodel(
                match_data, latest_state_data
            )
        )
        payload = json.dumps(latest_state_data.model_dump())
        logging.debug(f"Payload: {payload}")
        sse_message = f"event: state_update\nid: {event_id}\ndata: {payload}\n\n"
        yield sse_message

        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=None
                )
                if msg and msg["type"] == "message":
                    async with self.Session() as session:
                        latest_state_data: StateSchema = (
                            await read_data.read_latest_state_data(
                                self.match_id, session
                            )
                        )
                    latest_state_data: StateModel = (
                        data_converter.convert_stateschema_to_statemodel(
                            match_data, latest_state_data
                        )
                    )

                    payload = json.dumps(latest_state_data.model_dump())
                    event_id += 1

                    sse_message = (
                        f"event: state_update\nid: {event_id}\ndata: {payload}\n\n"
                    )
                    yield sse_message

        finally:
            logging.info("Unsubscribing from channel")
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
