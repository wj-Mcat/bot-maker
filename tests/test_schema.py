from __future__ import annotations
import asyncio
import pytest
from bot_maker.schema import User, DialogueState
from unittest import TestCase


@pytest.mark.asyncio
async def test_receive_message():
    user = User()
    asyncio.create_task(
        user.receive_message(
            message=DialogueState(
                intent=None,
                slots=None,
                text='a'
            )
        )
    )
    await user.wait_message()