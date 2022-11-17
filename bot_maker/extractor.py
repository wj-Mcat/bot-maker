from abc import abstractmethod
from typing import List, Dict, Optional
from copy import deepcopy
from bot_maker.schema import Message, EntityType, SystemEntity
from jieba.posseg import pair


class BaseExtractor:

    @abstractmethod
    async def extract(self, message: str) -> Message:
        raise NotImplementedError


class JieBaExtractor(BaseExtractor):

    @staticmethod
    def _parse(message: str) -> List[pair]:
        import jieba.posseg as psg
        pairs = psg.lcut(message)

        joined_pairs, temp_pair = [], deepcopy(pairs[0])

        for index in range(1, len(pairs)):
            if pairs[index].flag == temp_pair.flag:
                temp_pair.word += pairs[index].word
            else:
                joined_pairs.append(temp_pair)
                temp_pair = deepcopy(pairs[index])

        joined_pairs.append(temp_pair)

        return joined_pairs

    @staticmethod
    def _extract_time_tokens(pairs: List[pair]) -> List[str]:
        """
        extract time tokens
        Args:
            pairs:

        Returns: time tokens

        """
        time_tokens: List[str] = [item.word for item in pairs if item.flag in ['t', 'TIME']]
        return time_tokens

    @staticmethod
    def _extract_location_tokens(pairs: List[pair]) -> List[str]:
        """
        extract location tokens
        Args:
            pairs: the source of location pairs

        Returns: location tokens

        """
        location_tokens = [item.word for item in pairs if item.flag in ['ns', 'LOC']]
        return location_tokens

    async def extract(self, text: str) -> Optional[Message]:
        if not text:
            return None
        pairs = self._parse(text)
        message = Message.default(text)

        # 1. extract time slots & location slots, and add the first one into history state
        time_tokens = self._extract_time_tokens(pairs)
        message.add_slot(time_tokens[0], confidence=1, entity_name=SystemEntity.date.value, entity_type=EntityType.date)

        location_tokens = self._extract_location_tokens(pairs)
        message.add_slot(location_tokens[0], confidence=1, entity_name=SystemEntity.location.value, entity_type=EntityType.location)


class LTPExtractor(BaseExtractor):
    """
    TODO: add pyltp tools to extract information from text
    """
    async def extract(self, message: str) -> Message:
        pass
