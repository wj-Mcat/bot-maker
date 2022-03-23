from __future__ import annotations
from typing import List, Tuple, Union
from abc import ABC, abstractmethod
from bot_maker.schema import Intent, Message, Slot


class IntentServer(ABC):
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
    async def parse(self, message: str) -> Intent:
        raise NotImplementedError


class SlotFillingServer(ABC):
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
    async def parse(self, message: str) -> List[Slot]:
        raise NotImplementedError


class NLUServer:
    @abstractmethod
    async def parse(self, message: str) -> Tuple[Intent, List[Slot]]:
        raise NotImplementedError
    
    
class NLU:
    def __init__(self) -> None:
        self.intent_servers: List[IntentServer] = []
        self.slot_servers: List[SlotFillingServer] = []
        
        self.nlu_servers: List[NLUServer] = []
    
    async def parse(self, msg: str) -> Message:
        # 1. parse intent
        intent = None
        for intent_server in self.intent_servers:
            parsed_intent = await intent_server.parse(msg)
            # TODO: find the best intent based on intents
            intent = parsed_intent or intent
            if intent:
                break
        
        # 2. parse slots
        slots = []
        for slot_server in self.slot_servers:
            parsed_slots = await slot_server.parse(msg)
            if parsed_slots:
                slots.extend(parsed_slots)

        # 3. parse intent & slots from nlu servers

        nlu_intent, nlu_slots = await self.nlu_servers[0].parse(msg)
        if nlu_intent and not intent:
            intent = nlu_intent

        if nlu_slots:
            slots.extend(nlu_slots) 

        # 3. construct the message
        message = Message(
            intent=intent,
            slots=slots,
            text=msg
        )
        return message

    def use(self, servers: List[Union[IntentServer, SlotFillingServer, NLUServer]]) -> NLU:
        if not servers:
            raise ValueError('servers should not be empty or None')

        if not isinstance(servers, list):
            servers = [servers]
        
        for server in servers:
            if isinstance(server, IntentServer):
                self.intent_servers.append(server)
            elif isinstance(server, SlotFillingServer):
                self.slot_servers.append(server)
            elif isinstance(server, NLUServer):
                self.nlu_servers.append(server)
            else:
                raise TypeError(f'the type of server<{server}> is not correct.')
        return self
    