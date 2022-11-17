
# from bot_maker.nlu import NLUServer, RasaNLUServer
# from bot_maker.schema import Message, Intent


# class FakeNLUServer(NLUServer):
#     async def parse(self, text: str) -> Message:
#         if text == '我要定闹钟':
#             message = Message(
#                 intent=Intent()
#             )
#             return message


# def test_rasa_nlu_server():
#     server = RasaNLUServer(endpoint="http://dev.chatie.io:5005")

#     message = "帮我查一下北京现在的天气"
#     result = server.parse(message)
#     assert not not result


#     message = "token去哪儿买"
#     result = server.parse(message)
#     assert not not result


# def test_key_contains():
#     model = 'a'
#     dict_data = {
#         "a": 1
#     }
#     assert model in dict_data
