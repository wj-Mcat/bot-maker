
from unittest import IsolatedAsyncioTestCase
from bot_maker.schema import DialogueState
from bot_maker.nlu.base_nlu import KeywordIntentClassificationModel, KeywordSlotFillingModel



class BaseNLUTest(IsolatedAsyncioTestCase):

    async def test_keyword_intent_classification(self):
        model = KeywordIntentClassificationModel(
            corpus={
                "a": ['a-1', 'aa-1', 'aaa-1'],
                "b": ['b-1', 'bb-1', 'bbb-1'],
            }
        )
        intent = await model.parse_intent('aaaaa-1 b-1')
        assert intent.intent == 'a'

        model = KeywordIntentClassificationModel(
            corpus={
                "a": ['a-1', 'aa-1', 'aaa-1'],
                "b": ['b-1', 'bb-1', 'bbb-1'],
            }
        )
        intents = await model.parse_intents('aaaaa-1 b-1')
        assert len(intents) == 2
        assert intents[0].intent == 'a'
        assert intents[1].intent == 'b'

    async def test_keyword_slot_filling(self):
        model  = KeywordSlotFillingModel(
            corpus={
                "a": ['a-1', 'aa-1', 'aaa-1'],
                "b": ['b-1', 'bb-1', 'bbb-1'],
            }
        )
        
        sentence = "a-1 b-1"
        slots = await model.parse_slots(sentence)
        assert len(slots) == 2

        assert slots[0].entity.value == 'a-1'
        assert slots[0].name == 'a'
        