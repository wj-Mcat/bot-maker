import asyncio
import sys
sys.path.insert(0, '/Users/mcat/Code/myself-opensource/bot-maker')
from bot_maker.schema import Bot, Message, User
from bot_maker.maker import Task
from bot_maker.nlu import NLUServer, RasaNLUServer


class TerminalBot(Bot):
    def say(self, msg: str):
        print(f'>>> {msg}')


class TerminalUser(User):
    async def wait_message(self) -> str:
        message = input(">>> 用户:")
        return message


class FakeNLUServer(NLUServer):
    pass


class TerminalConversation(Task):
    @property
    def trigger_intent(self) -> str:
        return 'weather'

    def on_output_scope_intent(self):
        pass

    async def conversation(self, message: Message = None):
        all_slots = {}
        if not message:
            message = await self.wait_for_user()

        while True:
            if 'city' not in self.state.slots:
                self.bot.say('具体什么城市呢？')
                message = await self.wait_for_user()

            elif 'date' not in self.state.slots:
                self.bot.say('什么时候呢？')
                message = await self.wait_for_user()
            else:
                break

        print(f"将要查询{all_slots['city']}{all_slots['date']}的天气")


class HelloConversation(Task):
    @property
    def trigger_intent(self) -> str:
        return "intent_hello"

    def conversation(self):
        return "您好，我是吴京京的助手机器人，很愿意帮你们处理任何你们想处理的任何事情"

async def main():
    nlu_server = RasaNLUServer('http://dev.chatie.io:5005/')

    bot, user = TerminalBot(), TerminalUser()

    conversation = TerminalConversation(nlu=nlu_server, bot=bot, user=user)
    await conversation.conversation()


asyncio.run(main())