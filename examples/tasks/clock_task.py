from __future__ import annotations
from bot_maker.maker import Task
from bot_maker.schema import Message


class ClockTask(Task):

    @staticmethod
    def trigger_intent() -> str:
        return 'clock'

    async def conversation(self):
        while True:
            await self.wait_for_user()
            if 'time' not in self.state.slots:
                self.bot.say('请告诉我闹钟的具体时间')
            else:
                break

        await self.bot.say('非常感谢您的投诉举报，我们会有专门的工作人员跟进您投诉的内容')
