from bot_maker.maker import Task
from bot_maker.schema import Message

class ReturnVisitTask(Task):

    @staticmethod
    def trigger_intent():
        return 'return_visit'
    
    async def conversation(self):
        
        # 1. 具体位置共享
        while True:
            await self.bot.say('请问您这段时间有外出或位置具体变动吗？')
            message: Message = await self.wait_for_user()
            if message.intent.intent == 'deny':
                return
            if message.intent.intent == 'confirm':
                break
            
            await self.bot.say('对不起，我没有理解您具体的意思，是有变动还是没变动呢？')
        
        # 2. 更新用户的具体位置信息
        while True:
            if 'time' not in self.state:
                await self.bot.say('请问你您是什么时候外出的呢？')
                await self.wait_for_user()
            elif 'location' not in self.state:
                await self.bot.say('请问您是外出的具体地点是什么呢？')
                await self.wait_for_user()
            else:
                break
        
        # 3. 将从用户那里获取的具体位置信息更新到数据当中
        self.update_user_info(self.state)
        await self.bot.say('非常感谢您耐心的回复，您的相关信息我已经保存，后续会有相关人员持续跟踪！')
