# from unittest import TestCase
# from bot_maker.from_params import FromParams, Params
# from bot_maker.registrable import Registrable


# class FakeRegistrable(Registrable, FromParams):
#     pass


# class TestRegistrable(TestCase):
#     def test_registrable(self):
        
#         @FakeRegistrable.register("foo")
#         class Foo(FakeRegistrable):

#             def __init__(self, first: int = 1, second: int = 2) -> None:
#                 super().__init__()
#                 self.first = first
#                 self.second = second

        
#         params: Foo = Foo.from_params(Params(first=1, second=2))
#         params.first == 1

#         params: Foo = Foo.from_params(Params(first=3, second=2))
#         params.first == 3