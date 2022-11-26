from __future__ import annotations
import os
from typing import Dict, List, Optional, Tuple, Union, Any
from abc import ABC, abstractmethod

from wechaty_puppet import get_logger


from bot_maker.schema import Intent, Slot, Entity, DialogueState


logger = get_logger("BaseNLU")

class NLUModel(ABC):
    def fine_tune(self, train_args: Dict[str, Any]):
        pass

    def save(cache_dir: str) -> None:
        pass

    @classmethod
    def from_pretrained(cls, cache_dir: str) -> NLUModel:
        raise NotImplementedError

class IntentClassificationModel(NLUModel, ABC):
    """Intent Server which handle the intent parsing

    Input:
    Output:
        {
            "text": "我好像有点咳嗽",       // 待解析文本内容 
            "intent": {
                "id": 27424320,         // 意图唯一标识符
                "name": "sick",         // 意图关键字
                "confidence": 0.99968   // 模型解析信心分数
            }
        }
    """

    async def parse_intent(self, message: str) -> Optional[Intent]:
        intents = await self.parse_intents(message)
        return intents[0] if intents else None

    @abstractmethod
    async def parse_intents(self, message: str) -> List[Intent]:
        raise NotImplementedError


class KeywordIntentClassificationModel(IntentClassificationModel):
    def __init__(self, corpus: Dict[str, List[str]], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.intent2keywords = corpus
    
    async def parse_intents(self, message: str) -> List[Intent]:
        intents = {}
        for intent, keywords in self.intent2keywords.items():
            if any([True for keyword in keywords if keyword in message]):
                intents[intent] = Intent(
                    intent=intent,
                    confidence=1
                )
        return list(intents.values())


class SlotFillingModel(NLUModel, ABC):
    """Slot filling server which handle the slot filling process
    Input: {"text": message}
    Output: 
            {
                "text": "我好像有点咳嗽",
                "entities": [
                    {
                        "entity": "disease_name",     // 实体关键字
                        "start": 5,                   // 实体开始位置
                        "end": 7,                     // 实体结束位置
                        "confidence_entity": 0.97894, // 模型信心分数
                        "value": "咳嗽",              // 实体文本
                        "extractor": "ASNRIntentClassifier" // 抽取器类型
                    }
                ]
            }
    """

    @abstractmethod
    async def parse_slots(self, message: str) -> List[Slot]:
        raise NotImplementedError


class KeywordSlotFillingModel(SlotFillingModel):
    def __init__(self, corpus: Dict[str, List[str]], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        
        self.slot2keywords = corpus
    
    async def parse_slots(self, message: str) -> List[Slot]:
        slots = []
        for slot_name, keywords in self.slot2keywords.items():
            for keyword in keywords:
                if keyword in message:
                    slots.append(
                        Slot(
                            name=slot_name,
                            entity=Entity.from_sentence(keyword, slot_name, message)
                        )
                    )
        return slots
    

class NLUModel(ABC):
    INTENT_DIR: str = "nlu"
    SLOT_FILLING_DIR: str = 'slot_filling'
    
    def __init__(self, intent_model: Optional[IntentClassificationModel] = None, slot_filling_model: Optional[SlotFillingModel] = None) -> None:
        self.intent_model = intent_model
        self.slot_filling_model = slot_filling_model
    
    async def parse(self, message: str) -> Tuple[Optional[Intent], List[Slot]]:
        intents = []
        if self.intent_model is not None:
            intents = await self.intent_model.parse_intents(message)
        
        slots = []
        if self.slot_filling_model is not None:
            slots = await self.slot_filling_model.parse_slots(message)
        
        return intents, slots
    
    async def parse_dialogue_state(self, message: str) -> DialogueState:
        intents, slots = await self.parse(message)
        intent = intents[0] if intents else None
        return DialogueState(
            intent=intent,
            intents=intents,
            slots=slots,
            text=message
        )

    
class RemoteNLUModel:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    async def parse(self, message: str) -> Tuple[Optional[Intent], List[Slot]]:
        """parse nlu and model 

        Args:
            message (str): _description_

        Returns:
            Tuple[Optional[Intent], List[Slot]]: _description_
        """
    