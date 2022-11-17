from __future__ import annotations
import os
from typing import Dict, List, Optional, Tuple, Union, Any
from abc import ABC, abstractmethod

from wechaty_puppet import get_logger


from bot_maker.schema import Intent, Slot


logger = get_logger("BaseNLU")

class NLUModel(ABC):
    def fine_tune(self, train_args: Dict[str, Any]):
        pass

    def save(cache_dir: str) -> None:
        pass

    @classmethod
    def from_pretrained(cls, cache_dir: str) -> NLUModel:
        raise NotImplementedError

class IntentModel(NLUModel, ABC):
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
    @abstractmethod
    async def parse_intent(self, message: str) -> Optional[Intent]:
        raise NotImplementedError


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
    async def parse_slot_filling(self, message: str) -> List[Slot]:
        raise NotImplementedError


class NLUModel(ABC):
    INTENT_DIR: str = "nlu"
    SLOT_FILLING_DIR: str = 'slot_filling'
    
    def __init__(self, intent_model: Optional[IntentModel] = None, slot_filling_model: Optional[SlotFillingModel] = None) -> None:
        self.intent_model = intent_model
        self.slot_filling_model = slot_filling_model
    
    async def parse(self, message: str) -> Tuple[Optional[Intent], List[Slot]]:
        intent = None 
        if self.intent_model is not None:
            intent = await self.intent_model.parse_intent(message)
        
        slots = []
        if self.slot_filling_model is not None:
            slots = await self.slot_filling_model.parse_slot_filling(message)
        
        return intent, slots
    
    @staticmethod
    def from_pretrained(pretrained_path: str):
        intent_pretrained_dir = os.path.join(pretrained_path, NLUModel.INTENT_DIR)
        
        intent_model = None
        if os.path.exists(intent_pretrained_dir):
            logger.info("start to load intent modle from: %s", intent_pretrained_dir)
            intent_model = IntentModel
            

    def save_pretrained(self, pretrained_path: str):
        if self.intent_model is not None:
            self.intent_model.save_pretrained(pretrained_path)
        if self.slot_filling_model is not None:
            self.slot_filling_model.save_pretrained(pretrained_path)

    
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
    