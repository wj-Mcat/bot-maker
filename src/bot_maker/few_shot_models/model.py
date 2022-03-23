from __future__ import annotations
from abc import ABC
from typing import List, Tuple
from bot_maker.schema import Corpus, Intent, Slot


class FewShotModel(ABC):
    def train(self, corpus: List[Corpus]):
        pass

    @classmethod
    def from_file(cls, file_path: str):
        pass


class IntentModel(ABC):
    def predict(self, msg: str) -> Intent:
        pass


class SlotModel(ABC):
    def predict(self, msg: str) -> List[Slot]:
        pass


class NLUModel(IntentModel, SlotModel):

    def predict(self, msg: str) -> Tuple[Intent, List[Slot]]:
        pass
