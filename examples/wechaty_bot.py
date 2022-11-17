"""doc"""
import asyncio
import os
os.environ['token'] = 'wujingjing-ubuntu-server-padlocal-token'
from typing import Optional

from wechaty import Wechaty
from wechaty.user import Message

from bot_maker.maker import Maker
from bot_maker.maker import Task
from bot_maker.nlu.rasa_nlu import RasaNLUServer
from bot_maker.nlu.remote_slot import RemoteSlotFillingServer
from bot_maker.nlu.base_nlu import NLU


class SimpleChitchatTask(Task):
    def __init__(self, nlu: NLU, user: Optional[User] = None, bot: Optional[Bot] = None):
        super().__init__(nlu, user, bot)


# 1. define the rasa & slot server
rasa_server = RasaNLUServer(
    os.environ['rasa_nlu_server']
)
slot_server = RemoteSlotFillingServer(
    os.environ['slot_filling_server']
)


# 2. define the NLU module
nlu = NLU()
nlu.use([rasa_server, slot_server])

maker = Maker(nlu=nlu)

# 3. run with wechaty
async def message(msg: Message) -> None:
    """back on message"""
    from_contact = msg.talker()
    if from_contact.name != '秋客':
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
