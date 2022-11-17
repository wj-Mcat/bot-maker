from __future__ import annotations
from typing import Union


from bot_maker.nlu.base_nlu import NLUModel


class NLUServer:
    def __init__(self, model_or_pretrained_path: Union[NLUModel, str]) -> None:
        if isinstance(model_or_pretrained_path, str):
            NLUModel
        self.nlu_model = nlu
