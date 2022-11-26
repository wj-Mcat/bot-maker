from bot_maker.maker import Maker, Task


class FakeTask(Task):
    async def conversation(self):
        await self.wait_for_user()
        await self.bot.say("hello")
