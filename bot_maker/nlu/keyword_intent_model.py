from __future__ import annotations
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field
from collections import defaultdict

from wechaty_puppet import get_logger

from bot_maker.schema import Intent
from bot_maker.nlu.base_nlu import IntentModel


logger = get_logger("KeywordIntentModel")


@dataclass
class KeywordIntentInputExample:
    name: str
    keywords: List[str] = field(default_factory=list)


class KeywordIntentModel(IntentModel):

    def __init__(self, input_examples: List[KeywordIntentInputExample]) -> None:
        self.intent_keywords = defaultdict(set)
        for input_example in input_examples:
            self.intent_keywords[input_example.name] = set(input_example.keywords)

    async def parse_intent(self, message: str) -> Optional[Intent]:
        intent_names = set()
        for name, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    intent_names.add(name)
        
        if len(intent_names) > 1:
            logger.warning(
                'have parsed more than one intent<%s> and it will choice the first one as the final intent',
                ",".join(intent_names)
            )

        if len(intent_names) == 0:
            return None

        return Intent(
            intent=list(intent_names)[0]
        )
