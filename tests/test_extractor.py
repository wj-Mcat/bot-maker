from bot_maker.extractor import JieBaExtractor


def test_jieba_parse():
    sentence = '明天早上我准备起床'
    pairs = JieBaExtractor._parse(sentence)
    assert len(pairs) == 3


def test_jieba_time_extractor():
    sentence = '明天早上我准备起床'
    pairs = JieBaExtractor._parse(sentence)
    assert pairs[0].flag == 't'
    assert pairs[0].word == '明天早上'
