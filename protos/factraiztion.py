from nltk import word_tokenize
from nltk.stem import WordNetLemmatizer
from gensim.models.doc2vec import LabeledSentence
from gensim import models
from gensim import corpora
from gensim.matutils import corpus2csc
from collections import Counter
import pandas as pd
import numpy as np
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from multiprocessing import Pool
from sklearn.model_selection import GridSearchCV, ParameterGrid, StratifiedKFold, cross_val_predict
import xgboost as xgb
from lightgbm.sklearn import LGBMClassifier
from sklearn.metrics import log_loss, roc_auc_score
from pyfm import pylibfm

from logging import getLogger
logger = getLogger(__name__)

if __name__ == '__main__':
    from logging import StreamHandler, DEBUG, Formatter, FileHandler

    log_fmt = Formatter('%(asctime)s %(name)s %(lineno)d [%(levelname)s][%(funcName)s] %(message)s ')
    handler = FileHandler('tfidf_k.py.log', 'w')
    handler.setLevel(DEBUG)
    handler.setFormatter(log_fmt)
    logger.setLevel(DEBUG)
    logger.addHandler(handler)

    handler = StreamHandler()
    handler.setLevel('INFO')
    handler.setFormatter(log_fmt)
    logger.setLevel('INFO')
    logger.addHandler(handler)

    logger.info('load start')
    df_train = pd.read_csv('../data/train.csv')
    df_test = pd.read_csv('../data/test.csv')
    """
    x_train.to_csv('kernel_train.csv', index=False)
    x_test.to_csv('kernel_test.csv', index=False)
    """
    x = pd.read_csv('kernel_train.csv').values
    x_train = pd.read_csv('count_tfidf_train.csv').values

    with open('count_mat.pkl', 'rb') as f:
        count_mat = pickle.load(f)
    logger.info('count_mat {}'.format(count_mat.shape))
    with open('tfidf_mat.pkl', 'rb') as f:
        tfidf_mat = pickle.load(f)
    logger.info('tfidf_mat {}'.format(tfidf_mat.shape))
    train_num = x_train.shape[0]

    from scipy.sparse import hstack
    from tffm import TFFMClassifier
    import tensorflow as tf

    x_train = hstack([count_mat[:train_num], tfidf_mat[:train_num]], format='csr')
    x_test = hstack([count_mat[train_num:], tfidf_mat[train_num:]], format='csr')

    y_train = df_train['is_duplicate'].values
    logger.info('x_shape: {}'.format(x_train.shape))
    pos_rate = 0.165
    pos_num = y_train.sum()
    neg_num = y_train.shape[0] - y_train.sum()
    logger.info('pos_rate: %s, target pos_rate: %s, pos_num: %s' % (pos_num / y_train.shape[0], pos_rate, pos_num))

    w = (neg_num * pos_rate) / (pos_num * (1 - pos_rate))
    sample_weight = np.where(y_train == 1, w, 1)
    calc_pos_rate = (w * pos_num) / (w * pos_num + neg_num)
    logger.info('calc pos_rate: %s' % calc_pos_rate)

    logger.info('sampling start')

    from sklearn.cross_validation import train_test_split
    # x_train, x_valid, y_train, y_valid = train_test_split(x_train, y_train, test_size=0.2, random_state=4242)
    all_params = {'order': [6], 'rank': [10], 'n_epoch': [100], 'batch_size': [-1], 'init_std': [0.001], 'input_type': ['sparse']
                  }
    all_params = {'num_factors': [5, 10, 20],
                  'num_iter': [5, 10, 20, 100],
                  'verbose': [True],
                  'task': ["classification"],
                  'initial_learning_rate': [0.0001, 0.01, 0.001],
                  'learning_rate_schedule': ["optimal"]}
    min_score = (100, 100, 100)
    min_params = None
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=871)
    use_score = 0
    for params in ParameterGrid(all_params):
        list_score = []
        list_score2 = []
        list_best_iter = []

        for train, test in cv.split(x_train, y_train):
            trn_x = x_train[train]
            val_x = x_train[test]
            trn_y = y_train[train]
            val_y = y_train[test]
            trn_w = sample_weight[train]
            val_w = sample_weight[test]

            # reg = LogisticRegression(C=0.1, solver='sag', n_jobs=-1)
            # pred_x = cross_val_predict(reg, trn_x, trn_y, cv=5, n_jobs=-1)
            # trn_x = np.c_[trn_x, pred_x]
            """
            clf = TFFMClassifier(order=6,
                                 rank=10,
                                 optimizer=tf.train.AdagradOptimizer(0.01),
                                 n_epochs=100,
                                 batch_size=10000,
                                 init_std=0.001,
                                 input_type='sparse'
                                 )
            """
            clf = pylibfm.FM(**params)

            clf.fit(trn_x, trn_y)

            _score = log_loss(val_y, clf.predict(val_x), sample_weight=val_w)
            _score2 = - roc_auc_score(val_y, clf.predict(val_x), sample_weight=val_w)
            # logger.debug('   _score: %s' % _score)
            list_score.append(_score)
            list_score2.append(_score2)
            break
        score = (np.mean(list_score), np.min(list_score), np.max(list_score))
        score2 = (np.mean(list_score2), np.min(list_score2), np.max(list_score2))

        logger.info('param: %s' % (params))
        logger.info('loss: {} (avg min max {})'.format(score[use_score], score))
        logger.info('score: {} (avg min max {})'.format(score2[use_score], score2))
        if min_score[use_score] > score[use_score]:
            min_score = score
            min_score2 = score2
            min_params = params
        logger.info('best score: {} {}'.format(min_score[use_score], min_score))
        logger.info('best score2: {} {}'.format(min_score2[use_score], min_score2))
        logger.info('best_param: {}'.format(min_params))

    clf = pylibfm.FM(**min_params)
    clf.fit(x_train, y_train)

    p_test = clf.predict(x_test)
    sub = pd.DataFrame()
    sub['test_id'] = df_test['test_id']
    sub['is_duplicate'] = p_test
    sub.to_csv('submit.csv', index=False)
    logger.info('learn start')
    import xgboost as xgb
    params = {}
    params['objective'] = 'binary:logistic'
    params['eval_metric'] = 'logloss'
    params['eta'] = 0.02
    params['max_depth'] = 4

    """
    d_train = xgb.DMatrix(x_tra, label=y_tra, weight=trn_w)
    d_valid = xgb.DMatrix(x_val, label=y_val, weight=val_w)

    watchlist = [(d_train, 'train'), (d_valid, 'valid')]

    bst = xgb.train(params, d_train, 400, watchlist, early_stopping_rounds=50, verbose_eval=1)
    """
