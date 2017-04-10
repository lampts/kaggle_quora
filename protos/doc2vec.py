from nltk import word_tokenize
from nltk.stem import WordNetLemmatizer
from gensim.models.doc2vec import LabeledSentence
from gensim import models
import pandas
import numpy
import pickle
from multiprocessing import Pool

from logging import getLogger
logger = getLogger(__name__)

wnl = WordNetLemmatizer()
import aspell
from nltk.corpus import stopwords

asp = aspell.Speller('lang', 'en')
stops = set(stopwords.words("english")) | set(['?', ',', '.', ';', ':', '"', "'"])


def get(w):
    try:
        return asp.suggest(w)[0]
    except IndexError:
        return w


def split_into_words(text):
    return [wnl.lemmatize(t)
            for t in word_tokenize(text.lower())
            if t not in stops]
    """
    return [wnl.lemmatize(t) if t in asp
            else wnl.lemmatize(get(t))
            for t in word_tokenize(text.lower())
            if t not in stops]
    """


def doc_to_sentence(doc, name):
    words = split_into_words(doc)
    return LabeledSentence(words=words, tags=[name])


def corpus_to_sentences(df):
    p = Pool()
    ret = p.map(_load, enumerate(df.values))
    p.close()
    p.join()
    return ret


def _load(args):
    i, row = args
    if i % 10000 == 0:
        logger.info('sent %s/%s' % (i, 800000))
    return doc_to_sentence(row[1], row[0])


def load_data():

    df = pandas.read_csv('../data/train_clean2.csv')

    df1 = df[['qid1', 'question1']]
    df1.columns = ['qid', 'question']
    df2 = df[['qid2', 'question2']]
    df2.columns = ['qid', 'question']

    df_que = pandas.concat([df1, df2], ignore_index=True)
    df_que = df_que.drop_duplicates().fillna('').sort_values('qid')
    df_que['qid'] = ['TRAIN_%s' % i for i in df_que['qid']]

    df = pandas.read_csv('../data/test_clean2.csv')
    df1 = df[['question1']]
    df1.columns = ['question']
    df2 = df[['question2']]
    df2.columns = ['question']
    df_que2 = pandas.concat([df1, df2], ignore_index=True)
    df_que2 = df_que2.drop_duplicates().fillna('')
    df_que2['qid'] = ['TEST_%s' % i for i in numpy.arange(df_que2.shape[0])]

    df_que = pandas.concat([df_que, df_que2], ignore_index=True)
    logger.info('df_que {}'.format(df_que.shape))
    logger.info('start')
    sentences = corpus_to_sentences(df_que)
    with open('corpus.pkl', 'wb') as f:
        pickle.dump(sentences, f, -1)
    logger.info('sentences {}'.format(len(df_que)))
    logger.info('end load')
    return sentences


def train():

    logger.info('start')
    with open('corpus.pkl', 'rb') as f:
        sentences = pickle.load(f)
    logger.info('load end')

    model = models.Doc2Vec(sentences,
                           dm=0,
                           size=100,
                           window=5,
                           alpha=.025,
                           min_alpha=.025,
                           min_count=3,
                           sample=1e-6,
                           workers=16)
    """
    #model = models.Doc2Vec(sentences, size=100, window=8, min_count=3, workers=16)
    """
    logger.info('epoch')
    model.save('doc2vec.model')
    #model = models.Doc2Vec.load('doc2vec.model')

    for epoch in range(20):
        logger.info('Epoch: {} {}'.format(epoch + 1, model.min_alpha))
        model.train(sentences)
        model.alpha -= (0.025 - 0.0001) / 19
        model.min_alpha = model.alpha
        model.save('doc2vec.model')

    return model

if __name__ == '__main__':
    from logging import StreamHandler, DEBUG, Formatter, FileHandler

    log_fmt = Formatter('%(asctime)s %(name)s %(lineno)d [%(levelname)s][%(funcName)s] %(message)s ')
    handler = FileHandler('doc2vec.py.log', 'w')
    handler.setLevel(DEBUG)
    handler.setFormatter(log_fmt)
    logger.setLevel(DEBUG)
    logger.addHandler(handler)

    handler = StreamHandler()
    handler.setLevel('INFO')
    handler.setFormatter(log_fmt)
    logger.setLevel('INFO')
    logger.addHandler(handler)

    load_data()

    exit()

    # train()
    # with open('corpus.pkl', 'rb') as f:
    #    sentences = pickle.load(f)

    df = pandas.read_csv('../data/train.csv')

    df1 = df[['qid1', 'question1']]
    df1.columns = ['qid', 'question']
    df2 = df[['qid2', 'question2']]
    df2.columns = ['qid', 'question']

    df_que = pandas.concat([df1, df2], ignore_index=True)
    df_que = df_que.drop_duplicates().fillna('').sort_values('qid')
    df_que['qid'] = ['TRAIN_%s' % i for i in df_que['qid']]
    logger.info('df_que {}'.format(df_que.shape))

    model = models.Doc2Vec.load('doc2vec.model')

    df_vec = pandas.DataFrame(numpy.array([model.docvecs[qid] for qid in df_que['qid'].values]))
    df_vec['qid'] = df_que['qid'].values
    df_vec['question'] = df_que['question'].values

    #df_vec.to_csv('doc_vec.csv', index=False)
    with open('doc_vec.pkl', 'wb') as f:
        pickle.dump(df_vec, f, -1)

    df = pandas.read_csv('../data/test.csv')
    df1 = df[['question1']]
    df1.columns = ['question']
    df2 = df[['question2']]
    df2.columns = ['question']
    df_que2 = pandas.concat([df1, df2], ignore_index=True)
    df_que2 = df_que2.drop_duplicates().fillna('')
    df_que2['qid'] = ['TEST_%s' % i for i in numpy.arange(df_que2.shape[0])]

    df_vec = pandas.DataFrame(numpy.array([model.docvecs[qid] for qid in df_que2['qid'].values]))
    df_vec['qid'] = df_que2['qid'].values
    df_vec['question'] = df_que2['question'].values

    #df_vec.to_csv('doc_vec.csv', index=False)
    with open('doc_vec_test.pkl', 'wb') as f:
        pickle.dump(df_vec, f, -1)
