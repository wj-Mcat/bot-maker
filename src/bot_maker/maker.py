from __future__ import annotations

import asyncio
import os
from abc import abstractmethod
from datetime import datetime
from typing import Any, Type, List, Optional, Dict, Union

from wechaty import Contact, Room
from wechaty_puppet import FileBox

from bot_maker.nlu import NLUServer
from bot_maker.nlu.base_nlu import NLU
from bot_maker.schema import DialogueState, Bot, User, SlotField, Message, WechatyBot


class Task:
    def __init__(self, nlu: NLU, user: Optional[User] = None, bot: Optional[Bot] = None):
        self.bot = bot or Bot()
        self.user = user or User()

        self.nlu: NLU = nlu
        self.state = DialogueState()

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    async def wait_for_user(self):
        message = await self.user.wait_message()
        # message: Message = await self.nlu.parse(text)
        self.state.update(message)
        return message

    async def collect_form_data(self, slot_fields: List[SlotField]):
        # TODO: deep test form data collector
        turns: int = 0
        for slot_field in slot_fields:
            self.bot.say(slot_field.exception_msg)
            turns += 1

            if not self.state.get(slot_field.name):
                continue
            await self.wait_for_user()

    async def end_task(self):
        # save state to the db
        pass

    @staticmethod
    def trigger_intent() -> str:
        raise NotImplementedError

    def on_out_scope_intent(self):
        # TODO: process the out scope intent
        pass

    async def conversation(self):
        raise NotImplementedError

    async def activate(self, msg: str):
        message = await self.nlu.parse(msg)
        await self.user.receive_message(message=message)


class SingleTurnConversation:
    __conversations = {}

    @abstractmethod
    async def get_message(self, msg: str) -> str:
        raise NotImplementedError

    @staticmethod
    def register(key: str, conversation: SingleTurnConversation):
        SingleTurnConversation.__conversations[key] = conversation


class QAConversation(SingleTurnConversation):
    async def get_message(self, msg: str) -> str:
        return f'receive message: <{msg}>, and should the result from the QA models'


class ChitChatConversation(SingleTurnConversation):
    async def get_message(self, msg: str) -> str:
        return f'chitchat model response ...'


class Conversation:
    def __init__(self, task: Task, conversation_id: str, done_call_back) -> None:
        self.conversation_id = conversation_id
        self.start_time = datetime.now()
        self.task = task
        self.done_call_back = done_call_back

    async def say(self, message: str):
        await self.task.activate(message)

    async def start(self):
        await self.task.conversation()
        self.done_call_back(self.conversation_id)


class BotMessage:
    def __init__(self, msg_type: str) -> None:
        self.msg_type = msg_type

    @abstractmethod
    def get_message(self) -> Any:
        raise NotImplementedError


class StringBotMessage(BotMessage):
    def __init__(self, message: str) -> None:
        super().__init__('string')
        self.message = message

    def get_message(self) -> str:
        return self.message


class FileBoxBotMessage(BotMessage):
    def __init__(self, file_or_box: Union[str, FileBox]) -> None:
        super().__init__('file_box')

        if os.path.exists(file_or_box):
            file_or_box = FileBox.from_file(file_or_box)
        self.file_box = file_or_box

    def get_message(self) -> FileBox:
        return self.file_box


class Maker:
    def __init__(
            self,
            nlu: NLU,
            qa_conversation: Optional[SingleTurnConversation] = None,
            chitchat_conversation: Optional[SingleTurnConversation] = None,
    ) -> None:
        self._tasks: Dict[str, Type[Task]] = {}
        self.nlu = nlu
        self.conversations: Dict[str, Conversation] = {}

        self.qa_conversation = qa_conversation
        self.chitchat_conversation = chitchat_conversation

    def add_task(self, task: Type[Task]):
        if not issubclass(task, Task):
            raise TypeError(f'the type of task<{task}> is not correct.')
        if task.name() in self._tasks:
            raise ValueError(f'Task<{task.name()}> have been added into Maker.')
        self._tasks[task.name()] = task

    async def match_task(self, msg: str) -> Optional[Type[Task]]:
        message: Message = await self.nlu.parse(msg)

        # 1. match the task with trigger intent
        matched_task = None
        for task in self._tasks.values():
            if message.intent.intent == task.trigger_intent():
                matched_task = task
                break
        return matched_task

    def conversation_done_call_back(self, conversation_id: str):
        if conversation_id in self.conversations:
            self.conversations.pop(conversation_id)

    async def feed_message(self, msg: str, target_user: Union[Contact, Room]) -> Optional[str]:
        # 1. 如果已存在与用户之间的对话脚本
        conversation_id = None
        if isinstance(target_user, Contact):
            conversation_id = target_user.contact_id
        elif isinstance(target_user, Room):
            conversation_id = target_user.room_id
        else:
            raise ValueError(f'the type of target_user is not correct.')

        if conversation_id and conversation_id in self.conversations:
            await self.conversations[conversation_id].say(message=msg)
            return

        # 2. 创建对话脚本
        task_type: Optional[Type[Task]] = await self.match_task(msg)
        if task_type:
            # TODO: wechaty bot builder
            bot = WechatyBot(target_user)
            task = task_type(nlu=self.nlu, bot=bot)
            conversation = Conversation(task, conversation_id, done_call_back=self.conversation_done_call_back)
            self.conversations[conversation.conversation_id] = conversation
            asyncio.create_task(conversation.start())
            return

        # 3. QA & Chitchat
        if self.qa_conversation:
            result = await self.qa_conversation.get_message(msg)
            if result:
                return result
        if self.chitchat_conversation:
            result = await self.chitchat_conversation.get_message(msg)
            if result:
                return result
        return None
