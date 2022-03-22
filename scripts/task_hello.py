from bot_maker.maker import Task

class HelloTask(Task):

    @property
    def trigger_intent(self) -> str:
        return 'hello'

    def conversation(self):
        
        