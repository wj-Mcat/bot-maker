from __future__ import annotations
from typing import List, Optional, Tuple
from unicodedata import name
import requests

from bot_maker.schema import Entity, EntityType, Intent, Message, Slot, parse_intent, parse_slots
from bot_maker.nlu.base_nlu import NLUModel


class RasaNLUModel(NLUModel):

    def __init__(self, endpoint: str):
        if not endpoint.endswith('/'):
            endpoint += '/'
        if 'model/parse' not in endpoint:
            endpoint += 'model/parse'

        self.endpoint = endpoint

    async def parse(self, message: str) -> Tuple[Intent, List[Slot]]:
        result = requests.post(self.endpoint, json=dict(text=message)).json()
        if not result:
            return None
        
        intent = parse_intent(result)
        slots = parse_slots(result)
        return intent, slots
