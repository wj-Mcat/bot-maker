# from __future__ import annotations
# import unittest

# from bot_maker.from_params import FromParams, Params


# class FromParamTest(unittest.TestCase):
#     def test_from_params(self):
#         my_class = MyClass.from_params(Params({"my_int": 10}), my_bool=True)

#         assert isinstance(my_class, MyClass)
#         assert my_class.my_int == 10
#         assert my_class.my_bool


# class MyClass(FromParams):
#     def __init__(self, my_int: int, my_bool: bool = False) -> None:
#         self.my_int = my_int
#         self.my_bool = my_bool


# class Foo(FromParams):
#     def __init__(self, a: int = 1) -> None:
#         self.a = a


# class Bar(FromParams):
#     def __init__(self, foo: Foo) -> None:
#         self.foo = foo
