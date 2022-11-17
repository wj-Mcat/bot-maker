"""
Bot Maker - https://github.com/wj-Mcat/bot-maker

Authors:   Jingjing WU (吴京京) <https://github.com/wj-Mcat>

2022-now @ Copyright wj-Mcat

Licensed under the Apache License, Version 2.0 (the 'License');
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an 'AS IS' BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from __future__ import annotations
from asyncio import Event
from typing import List, Union, Optional, Dict
from enum import Enum
from datetime import datetime
from dataclasses import dataclass

from wechaty import Contact, Room

UNKNOWN_INTENT = 'unknown_intent'


class SystemEntity(Enum):
    date = 'sys_date'
    location = 'sys_location'
    int = "sys_int"
    float = "sys_float"
    datetime = "sys_datetime"


class EntityType(Enum):
    float = 0
    date = 1
    datetime = 2
    text = 3
    location = 4


@dataclass
class Intent:
    intent: str
    confidence: float = 1

    @staticmethod
    def default():
        return Intent(intent=UNKNOWN_INTENT)
    
    def is_unknown(self) -> bool:
        return self.intent == UNKNOWN_INTENT 


@dataclass
class Entity:
    value: str
    entity: str
    confidence: float
    type: EntityType

    start_offset: int = 0
    end_offset: int = 0


@dataclass
class Slot:
    name: str
    entity: Entity


@dataclass
class SlotField:
    """Form task which should be collected within form mode"""
    name: str
    exception_msg: str
    required: bool = True
    max_turns: int = 3


@dataclass
class Message:
    intent: Intent                      # 一个文本中只允许有一个意图
    slots: List[Slot]              # 抽取出的实体数据
    text: str
    datetime: datetime = datetime.now() # 默认当前时间

    @property
    def slots_names(self) -> List[str]:
        return [slot.name for slot in self.slots]

    def add_slot(
        self, value: str, confidence: float,
        entity_name: str, entity_type: EntityType,
        slot_name: str = None, force_update: bool = False
    ):
        slot_name = slot_name or entity_name

        # 1. checking the existing slot name
        if not [True for slot in self.slots if slot.name == slot_name] and not force_update:
            return

        # 2. constructing text content
        entity = Entity(
            value=value,
            entity=entity_name,
            confidence=confidence,
            type=entity_type
        )
        slot = Slot(
            name=slot_name,
            entity=entity
        )
        self.slots.append(slot)

    @staticmethod
    def default(text: str) -> Message:
        return Message(
            intent=Intent.default(),
            slots=[],
            text=text
        )


@dataclass
class Corpus:
    text: str
    intent: Intent
    entities: List[Entity]


class DialogueState:
    def __init__(self):
        self.slots: Dict[str, Slot] = {}
        self.history_messages: List[Message] = []

    def update(self, message: Message):
        for slot in message.slots:
            self.slots[slot.name] = slot

        self.history_messages.append(message)

    def get(self, slot_name: str) -> Optional[Slot]:
        return self.slots.get(slot_name, None)
    
    def latest_message(self) -> Optional[Message]:
        if not self.history_messages:
            return None
        return self.history_messages[-1]


prefix = '>>> '


class User:
    def __init__(self, event: Optional[Event] = None) -> None:
        self.event = event or Event()
        self._messages = []
        
    async def wait_message(self) -> Message:
        await self.event.wait()
        # TODO: how to handle the multi-message at the same time
        message = self._messages[-1]

        # clear the messages box
        self._messages = []
        self.event.clear()
        return message 

    async def receive_message(self, message: Message):
        self._messages.append(message)
        self.event.set()


class Bot:
    async def say(self, msg: str):
        raise NotImplementedError


class WechatyBot(Bot):

    def __init__(self, conversation: Union[Contact, Room]) -> None:
        super().__init__()
        self.conversation = conversation

    async def say(self, msg: str):
        await self.conversation.say(msg)


class TerminalBot(Bot):
    def say(self, msg: str):
        print(msg)


class TerminalUser(User):
    async def wait_message(self):
        message = input(prefix + 'User:')
        return message


def parse_intent(json_data: dict) -> Intent:
    intent = Intent(
        json_data['intent']['name'],
        confidence=1,
    )
    return intent


def parse_slots(json_data: dict) -> List[Slot]:
    slots = []
    for entity in json_data['entities']:
        slots.append(Slot(
            name=entity['entity'],
            entity=Entity(
                value=entity['value'],
                entity=entity['entity'],
                confidence=entity['confidence_entity'],
                # TODO: add data type detection function
                type=EntityType.text
            )
        ))
    return slots
