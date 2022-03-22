from bot_maker.maker import Task
from bot_maker.schema import Message

class ComplaintTask(Task):

    @staticmethod
    def trigger_intent() -> str:
        return 'complaint'

    async def on_output_scope_intent(self):
        await self.bot.say('当前正在为您处理投诉的任务，请问您确定要结束此任务吗？')
        message: Message = await self.wait_for_user()
        if message.intent.intent == 'affirm':
            await self.end_task()
            
        elif not message.intent.intent == 'deny':
            await self.on_output_scope_intent()
        
    async def conversation(self):
        # 处理核心对话逻辑
        while True:
            await self.bot.say('请问您还有继续投诉的内容吗？如果有的话请继续阐述，我会记录您所有的投诉内容！')
            message: Message = await self.wait_for_user()
            if message.intent.intent == 'deny':
                break
            # db.session.add(message)
            # db.session.commit()

        await self.bot.say('非常感谢您的投诉举报，我们会有专门的工作人员跟进您投诉的内容')
    