from __future__ import annotations

from typing import List
import json
from dataclasses import dataclass


@dataclass
class FAQInputExample:
    """simple faq input example"""
    questions: List[str]
    answer: str


@dataclass
class FAQConfig:
    corpus_file: str
    model_name: str


class FAQ:
    def __init__(self, config: FAQConfig) -> None:
        self.config = config
    
    @staticmethod
    def read_examples(file: str) -> List[FAQInputExample]:
        with open(file, 'r', encoding='utf-8') as f:
            example_dicts = json.load(f)
        
        examples = []
        for example_dict in example_dicts:
            examples.append(
                FAQInputExample(**example_dict)
            )
        return examples
            
    def predict(self, query: str) -> str:
        raise NotImplementedError
