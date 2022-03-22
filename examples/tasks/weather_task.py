from __future__ import annotations
from bot_maker.maker import Task


class WeatherTask(Task):

    @staticmethod
    def trigger_intent() -> str:
        return 'weather'

    async def conversation(self):
        while True:
            if 'location' not in self.state.slots:
                await self.bot.say('请问所在城市是哪里呢？')
            elif 'time' not in self.state.slots:
                await self.bot.say('请问您想咨询什么时候的天气呢？')
            else:
                break
            await self.user.wait_message()

        time, location = self.state.get('time'), self.state.get('location')
        await self.bot.say(f'即将为您查询{time}-{location}的天气情况 ...')
