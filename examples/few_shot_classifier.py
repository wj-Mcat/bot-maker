from __future__ import annotations
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional
from paddlenlp import Taskflow
from dataclasses import dataclass, field



@dataclass
class SupportSet:
    sentences: List[str]
    label: str
    answer: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class FewShotTextClassificationCorpus:
    def __init__(self, support_sets: List[SupportSet]) -> None:
        self.support_sets = support_sets
        self.batch_size = 4

        # sentence to label
        self.sentence2label = self._sentene_to_labels()
        self.label2supportset = {item.label: item for item in support_sets}
    
    def _sentene_to_labels(self):
        sentence2label = {}
        for support_set in self.support_sets:
            for sentence in support_set.sentences:
                sentence2label[sentence] = support_set.label
        return sentence2label
    
    def construct_inputs(self, query: str):
        inputs = []
        for support_set in self.support_sets:
            inputs.extend(
                [[query, sentence] for sentence in support_set.sentences]
            )
        
        return inputs
    
    @staticmethod
    def from_json_file(file: str) -> FewShotTextClassificationCorpus:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        support_sets = []
        for item in data:
            support_sets.append(
                SupportSet(**item)
            )
        return FewShotTextClassificationCorpus(support_sets)
        

class FewShotModel:
    def __init__(self, corpus: FewShotTextClassificationCorpus) -> None:
        self.corpus = corpus
        self.model = Taskflow("text_similarity", model='simbert-base-chinese')
        self.threshold: float = 0.7
    
    def _choice_top_1_result(self, result: List[dict]) -> Optional[dict]:
        sentence, score = "", 0
        for item in result:
            if item['similarity'] > score:
                score = item['similarity']
                sentence = item['text2']
        if score < self.threshold:
            return None
        return sentence
    
    def predict(self, query: str) -> Optional[str]:
        inputs = self.corpus.construct_inputs(query)
        result = self.model(inputs)
        sentence = self._choice_top_1_result(result)
        if sentence is None:
            return None

        label = self.corpus.sentence2label[sentence]
        return label
    
    def get_answer_online(self, query: str, sentences: Dict[str, List[str]]) -> Optional[str]:
        corpus = FewShotTextClassificationCorpus()
        label = self.predict(query)
        if not label:
            return None
        support = self.corpus.label2supportset[label]
        return support
    def get_answer(self, query: str) -> Optional[str]:
        label = self.predict(query)
        if not label:
            return None
        support = self.corpus.label2supportset[label]
        return support


from flask import Flask, request, jsonify

app = Flask(__name__)

corpus = FewShotTextClassificationCorpus.from_json_file('corpus.json')
model = FewShotModel(corpus)


@app.route("/predict", methods=['POST'])
def get_answer_online():
    data = request.get_json()
    support_set = model.get_answer(data['query'])
    return jsonify(support_set)

@app.route("/predict", methods=['POST'])
def get_answer():
    data = request.get_json()
    support_set = model.get_answer(data['query'])
    return jsonify(support_set)



app.run(host='0.0.0.0', port=8005)

corpus = [{
    "sentences": [
        '明天早上叫起床',
        '明天叫我起床',
        '定一个明天早上起床的闹钟',
        '明天早上'
    ],
    "slots": {
        "time": "时间"
    },
    "intent": "clock"
}, {
    "sentences": [
        '明天早上叫起床',
        '明天叫我起床',
        '定一个明天早上起床的闹钟',
        '明天早上'
    ],
    "intent": "clock"
}]
