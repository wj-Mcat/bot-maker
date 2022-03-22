"""doc"""
import asyncio
import imp
import logging
import os
from re import L
from typing import Optional, Union

from wechaty_puppet import FileBox

from wechaty import Wechaty, Contact
from wechaty.user import Message, Room

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(filename)s <%(funcName)s> %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

log = logging.getLogger(__name__)
from bot_maker.maker import Maker
from bot_maker.nlu.rasa_nlu import RasaNLUServer
from bot_maker.nlu.remote_slot import RemoteSlotFillingServer
from bot_maker.nlu.base_nlu import NLU

rasa_server = RasaNLUServer(
    os.environ['rasa_nlu_server']
)
slot_server = RemoteSlotFillingServer(
    os.environ['slot_filling_server']
)

nlu = NLU()
nlu.use([rasa_server, slot_server])

maker = Maker(
    nlu=nlu,
)
from examples.tasks.return_visit_task import ReturnVisitTask
from examples.tasks.complaint_task import ComplaintTask
from examples.tasks.greet_task import GreetTask

maker.add_task(ReturnVisitTask)
maker.add_task(ComplaintTask)
maker.add_task(GreetTask)


async def message(msg: Message) -> None:
    """back on message"""
    from_contact = msg.talker()
    if not from_contact.name == '秋客':
        return
    text = msg.text()
    await maker.feed_message(text, target_user=from_contact)

bot: Optional[Wechaty] = None


async def main() -> None:
    """doc"""
    # pylint: disable=W0603
    global bot
    bot = Wechaty().on('message', message)
    await bot.start()


asyncio.run(main())
