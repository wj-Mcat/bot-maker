from quart import Quart
from bot_maker.nlu.base_nlu import NLUModel, KeywordIntentClassificationModel, KeywordSlotFillingModel
from bot_maker.maker import Task, Maker
from bot_maker.schema import DialogueState

class GreetTask(Task):
    @staticmethod
    def trigger_intent() -> str:
        return 'greet'
        
    async def conversation(self):

        # 处理核心对话逻辑
        await self.bot.say('您好啊，我是小猫的个人助理')
        msg = await self.wait_for_user()
    
class StockTask(Task):

    @staticmethod
    def trigger_intent() -> str:
        return "search_stock"

    async def conversation(self):
        await self.bot.say("你好啊")
        await self.wait_for_user()
        
        while True:
            if 'stock' not in self.state:
                await self.bot.say("请告知我具体股票是什么，比如: 通威股份")
            elif 'roe' not in self.state:
                await self.bot.say("请告知我具体数值是什么，比如: ROE、PE")
            else:
                break
        
        await self.bot.say("已查询")
        

maker = Maker(
    nlu=NLUModel(
        intent_model=KeywordIntentClassificationModel({
            'hello': ['你好啊', '你好'],
            'help': ['帮助'],
            "search_stock": "帮我查股票"
        }),
        slot_filling_model=KeywordSlotFillingModel({
            'stock': ['通威股份', '新东方在线'],
            'metric': ['roe']
        })
    )
)

maker.add_task(StockTask)


app = Quart(__name__)

@app.route("/send/<string:msg>", methods=['GET'])
async def send(msg: str):
    await maker.feed_message(msg, target_user='test-id')
    

app.run()