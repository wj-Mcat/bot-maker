from __future__ import annotations

from typing import List

import requests

from bot_maker.nlu.base_nlu import SlotFillingServer
from bot_maker.schema import Slot, parse_slots


class RemoteSlotFillingServer(SlotFillingServer):
    def __init__(self, endpoint: str):
        # TODO: define the slot filling server endpoint
        if not endpoint.endswith('/'):
            endpoint += '/'

        self.endpoint = endpoint

    async def parse(self, message: str) -> List[Slot]:
        result = requests.post(self.endpoint, json=dict(text=message)).json()
        if not result:
            return []
        slots = parse_slots(result)
        return slots
