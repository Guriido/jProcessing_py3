from jNlp.jTokenize import jTokenize
from jNlp.edict_search_monash.edict_search import *
import json
from jNlp.jProcessing import long_substr
from jNlp.unicode_block import Block
from jNlp.jCabocha import cabocha
from bs4 import BeautifulSoup
import re


class Translator(object):

    def __init__(self, edict_path, specialdict_path=None):

        self.parser = Parser(edict_path)
        self.dict = None
        self.block = Block()
        if specialdict_path is not None:
            file = open(specialdict_path, 'r')
            self.dict = json.load(file)
        self.categories = {'full katakana': 1, 'full hiragana': 2, 'hiragana + kanji': 3, 'full latin': 4, 'other': 5}

    def parse(self, sentence):
        """
        takes a japanese sentence as input, returns a list of meanings corresponding to each word

        :param sentence: list of string
        :return: list of list of string
        """
        meanings = []  # words need to be seperated
        tree = BeautifulSoup(cabocha(sentence), features="xml")
        print(cabocha(sentence))
        for chunk in tree.sentence.findAll("chunk"):
            for token in chunk.findAll("tok"):
                feature = token.get("feature")
                features = feature.split(',')
                name = token.string
                if name in self.dict.keys():
                    # Case particle of special character
                    if len(self.dict[name]) == 1 and self.dict[name][0] == '':
                        pass
                    else:
                        meanings.append({'japanese': name, 1: self.dict[name]})
                else:
                    # categories: full katakana, full hiragana, kanas+kanjis, full latin, other
                    metablock = self.string_metablock(name)
                    if metablock == self.categories['full latin']:
                        meanings.append({'japanese': name, 1: [name]})
                    elif features[0] == "助動詞":
                        pass
                    else:
                        query = features[6]
                        search = self.parser.search(query)

                        bypass_translation = len(search) == 0
                        # if query == '神保':
                        #     print(bypass_translation)
                        if not bypass_translation:
                            entry = get_most_precise_entry(search, query)
                            translations = get_meanings(entry.glosses)
                            #  exceptional rule -> ある＝いる
                            if query == 'いる':
                                cpt = 1
                                while cpt in translations.keys():
                                    cpt += 1
                                cpt_max = cpt
                                search_bis = self.parser.search('ある')
                                entry_bis = get_most_precise_entry(search_bis, query)
                                translations_bis = get_meanings(entry_bis.glosses)
                                cpt = 1
                                while cpt in translations_bis.keys():
                                    translations[cpt_max] = translations_bis[cpt]
                                    cpt_max += 1
                                    cpt += 1
                            translations['japanese'] = query
                            if features[0] == '名詞':
                                translations['pos_tag'] = 'NN'
                            elif features[0] == '動詞':
                                translations['pos_tag'] = 'VB'

                        if bypass_translation:
                            if features[1] == '固有名詞' and features[2] == '人名':
                                translations = {'japanese': query, 1: '$PERSON'}  # special flag: english POS TAG necessary for translation
                            elif features[1] == '固有名詞' and features[2] == '地域':
                                translations = {'japanese': query, 1: '$LOCATION'}
                            else:
                                translations = None
                        if translations is not None:
                            meanings.append(translations)

        return meanings

    def string_metablock(self, string):
        """
        returns the id of the category of the unicode metablock of input string
        :param string: str
        :return: int (id of metablock)
        """

        katakana, hiragana, kanji, latin = False, False, False, False
        for character in string:
            block_name = self.block.block(character)
            if block_name == 'Hiragana':
                hiragana = True
            elif block_name == 'Katakana':
                katakana = True
            elif block_name == 'CJK Unified Ideographs':
                kanji = True
            elif block_name == 'Basic Latin':
                latin = True
            else:
                return self.categories['other']
        if latin:
            if not (hiragana or kanji or katakana):
                return self.categories['full latin']
            else:
                return self.categories['other']
        elif katakana:
            if not (hiragana or kanji):
                return self.categories['full katakana']
            else:
                return self.categories['other']
        elif kanji:
            return self.categories['hiragana + kanji']
        else:
            return self.categories['full hiragana']


def get_most_precise_entry(list_of_entries, query):
    """
    returns the closest entry of the list to the query, according to the following score:
    score = len(longest_substring) / max(len(query), len(entry))
    :param list_of_entries: list of entries (output of the search)
    :param query: string
    :return: entry object
    """
    if list_of_entries is None or len(list_of_entries) == 0:
        return None
    max_score, indice = 0, 0
    for i, entry in enumerate(list_of_entries):
        score = len(long_substr(query, entry.japanese)) / max(len(query), len(entry.japanese))
        if score > max_score:
            max_score = score
            indice = i
    return list_of_entries[indice]


def get_meanings(search_glosses):
    """
    returns a cleanly parsed dict of meanings of the entry, from its glosses
    :param search_glosses: list of string (glosses of a entry)
    :return: dict of list of string
    """
    # list_of_string = search[0].glosses
    meanings = {}
    synonyms = []
    current_meaning_id = 1
    # print(search_glosses[0:-1])
    for string in search_glosses:
        stripped = string.strip()  # remove beginning and end whitespaces
        while stripped and stripped[0] == '(':

            # print('( + digit !')
            [element, reste] = stripped[1:].split(')', 1)
            if element and element.isdigit():
                digit = int(element)
                if digit > current_meaning_id:
                    meanings[current_meaning_id] = synonyms
                    synonyms = []
                    current_meaning_id += 1
            stripped = reste.strip()
            # print(digit, reste)
        # removing the substrings '(..)' and '{..}'
        regex = re.compile('[(].*[)]|{.*}')
        stripped = regex.sub('', stripped).strip()
        if stripped:
            stripped = stripped.split('(', 1)[0].strip()
            stripped = stripped.replace('to ', '').strip()
            synonyms.append(stripped)
    meanings[current_meaning_id] = synonyms
    return meanings