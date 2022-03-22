from __future__ import annotations
from typing import List, Optional, Tuple
from unicodedata import name
import requests

from bot_maker.schema import Slot, parse_slots
from bot_maker.nlu.base_nlu import NLUServer, SlotFillingServer


class RemoteSlotFillingServer(SlotFillingServer):
    def __init__(self, endpoint: str):
        # TODO: define the slot filling server enndpoint
        if not endpoint.endswith('/'):
            endpoint += '/'

        self.endpoint = endpoint

    async def parse(self, message: str) -> List[Slot]:
        result = requests.post(self.endpoint, json=dict(text=message)).json()
        if not result:
            return None
        slots = parse_slots(result)
        return slots
