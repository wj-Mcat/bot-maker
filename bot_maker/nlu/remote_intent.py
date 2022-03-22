from __future__
from __future__ import annotations
from typing import Optional
import requests

from bot_maker.schema import Message, parse_intent
from bot_maker.nlu.base_nlu import IntentServer


class RemoteIntentServer(IntentServer):
    def __init__(self) -> None:
        super().__init__()

    async def parse(self, message: str) -> Optional[Message]:
        result = requests.post(self.endpoint, json=dict(text=message)).json()
        if not result:
            return None
        intent = parse_intent(result)
        return intent