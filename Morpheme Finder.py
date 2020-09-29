from collections import defaultdict
from tqdm import tqdm
from requests import request, ConnectionError
from json import loads

word_dict = defaultdict(None)
label_func = defaultdict(None)
known_prefixes = set()
known_suffixes = set()

EVQR_AFFIX = '<evqr.affix>'
PREFIX_AND_SUFFIX = '<prefix.and.suffix>'
VOWEL = '<vowel>'

try:
    with open('.env.json') as f:
        ENV_VARIABLES = loads(f.read())
        f.close()
except FileNotFoundError:
    ENV_VARIABLES = {'DATA_DIR': '<path to ur data folder>'}
DATA_DIR = ENV_VARIABLES['DATA_DIR']
FTP_DIR = 'http://m106.nthu.edu.tw/~s106062341/morpheme_finder_data/'


class Word:

    @staticmethod
    def create_synonym_postfix(word, delete=None, append=None):
        return f'{word}{f"--{delete}--" if delete is not None else ""}{f"++{append}++" if append is not None else ""}'

    @staticmethod
    def create_synonym_prefix(word, delete=None, append=None):
        return f'{f"--{delete}--" if delete is not None else ""}{f"++{append}++" if append is not None else ""}{word}'

    @staticmethod
    def letter_cmp(a, b):
        divider = 0
        for i, (letter_a, letter_b) in enumerate(zip(a, b)):
            if letter_a != letter_b:
                divider = i
        return min(divider, len(a), len(b))

    def __init__(self, text, affix_list):
        self.text = text
        self.affix_list = affix_list
        self.synonym = defaultdict(None)
        self.label = defaultdict(None)

    @property
    def count(self):
        return sum([c for c in self.synonym.values()])

    def create_label(self, label_name, *args):
        if label_name not in label_func:
            return False
        self.label[label_name] = label_func[label_name](self, *args)
        return True


def get_file(filename: str, callback: classmethod) -> bool:
    try:
        with open(f'{DATA_DIR}{filename}', 'r') as f:
            callback(f.read())
            f.close()
            return True
    except FileNotFoundError:
        try:
            res = request('GET', f'{FTP_DIR}{filename}')
            res.encoding = 'Big5'
            callback(res.text)
            return True
        except ConnectionError:
            print('HTTP connection failed')
            return False
        except Exception as e:
            print(f'Load failed: {e}')
            return False


def load_vocabulary():
    def callback(content):
        for line in content.split('\n')[1:-1]:
            word, *affix_list = line.replace('-', '').split(' ')[:-1]
            word_dict[word] = (Word(word, affix_list))
    if get_file('EVQR.word.and.affix.txt', callback):
        print('Load done')


def load_prefix_and_suffix():

    def prefix_callback(content):
        for line in content.split('\n')[1:-1]:
            known_prefixes.update(filter(lambda x: len(x) > 0, line[:-1].strip().replace('-', '').split(', ')))

    def suffix_callback(content):
        for line in content.split('\n'):
            known_suffixes.update(filter(lambda x: len(x) > 0, line[:-1].strip().replace('-', '').split(', ')))

    if get_file('prefixes.txt', prefix_callback) and get_file('suffixes.txt', suffix_callback):
        print('Load prefixes & suffixes done')


def mapping_label_func():
    def evqr_affix(word):
        text = word.text
        label = [0] * len(text)
        pos = 0
        for affix in word.affix_list:
            if affix.lower() in text:
                label[text.find(affix, pos)] = 1 if pos != 0 else 0
                pos = text.find(affix, pos) + len(affix)
            else:
                k = Word.letter_cmp(text[pos:], affix)
                if k > 1:
                    label[pos] = 1 if pos != 0 else 0
                    pos += 1

        return [t for t in zip(text, label)]

    def vowel(word):
        vowels = {"a", "e", "i", "o", "u"}
        return [(letter, int(letter in vowels)) for letter in word.text]

    def prefix_and_suffix(word):
        word_len = len(word.text)
        label = [0] * word_len

        for i in range(word_len):
            pattern = word.text[:word_len - 1 - i]
            if pattern in known_prefixes:
                label[len(pattern)] = 1

        for i in range(word_len):
            pattern = word.text[i + 1:]
            if pattern in known_suffixes:
                label[i] = 2 if label[i] == 0 else 3

        return [t for t in zip(word.text, label)]

    label_func[EVQR_AFFIX] = evqr_affix
    label_func[VOWEL] = vowel
    label_func[PREFIX_AND_SUFFIX] = prefix_and_suffix
    print('Mapping done')


def create_label_data():
    for word in tqdm(word_dict.values()):
        if not word.create_label(EVQR_AFFIX):
            print('Failed at label with EVQR.affix')
            return False
        if not word.create_label(VOWEL):
            print('Failed at label with Vowel')
            return False
        if not word.create_label(PREFIX_AND_SUFFIX):
            print('Failed at label with prefix & suffix')
            return False
    print('Label done')
    return True


if __name__ == '__main__':
    load_vocabulary()
    load_prefix_and_suffix()
    mapping_label_func()
    if create_label_data():
        for w in word_dict.values():
            print(w.label[EVQR_AFFIX])  # data base on EVQR.word.and.suffix.txt
            # print(w.label[PREFIX_AND_SUFFIX])  # data base on prefixes.txt & suffixes.txt
            # print(w.label[VOWEL])  # data base on vowel's position in the word
