from __future__
from __future__ import annotations
import imp

from typing import Optional, List

from bot_maker.maker import Task
from bot_maker.schema import Message

class NotificationJob(Job):
    def get_notification(self, location_id: int) -> Optional[str]:
        # 根据地理位置信息获取用户列表信息
        notifications = db.Notification.query.filter(Notification.location_id == location_id)
        if not notifications:
            return
        joined_notification = ';'.join([notification.msg for notification in notifications])
        return joined_notification
    
    def get_persons(self, location_id: int) -> List[Person]:
        # 根据位置获取辖区所在用户列表信息
        persons = db.Person.query.filter(Person.location_id == location_id)
        return persons or []

    def send(self, location_id: int):
        """send notification to the person in the location

        Args:
            location_id (int): the location_id
        """
        # 1. 根据位置获取档期的疫情通知 
        notification = self.get_notification(location_id)
        if not notification:
            return
        
        # 2. 根据位置获取所在区域的用户列表
        persons = self.get_persons(location_id)
        if not persons:        
            return

        # 3. 将疫情通知消息发送给区域用户
        for person in persons:
            self.channel.send_msg(person, notification)
        
class ReturnVisitTask(Task):

    @staticmethod
    def trigger_intent():
        return 'every_week'
    
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



