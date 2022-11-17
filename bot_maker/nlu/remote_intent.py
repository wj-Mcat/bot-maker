from __future__ import annotations

from typing import Optional

import requests

from bot_maker.nlu.base_nlu import Intent
from bot_maker.schema import parse_intent, Intent


class RemoteIntentServer(Intent):
    def __init__(self, endpoint: str) -> None:
        super().__init__(
        self.endpoint = endpoint

    async def parse(self, message: str) -> Optional[Intent]:
        result = requests.post(self.endpoint, json=dict(text=message)).json()
        if not result:
            return None
        intent = parse_intent(result)
        return intent
