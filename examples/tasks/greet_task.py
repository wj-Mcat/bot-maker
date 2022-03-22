from bot_maker.maker import Task
from bot_maker.schema import Message

class GreetTask(Task):
    @staticmethod
    def trigger_intent() -> str:
        return 'greet'
        
    async def conversation(self):
        # 处理核心对话逻辑
        await self.bot.say('您好啊，我是小猫的个人助理')