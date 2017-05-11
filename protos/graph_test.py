from itertools import combinations
from tqdm import tqdm
import pickle
import pandas
import numpy

from scipy.stats import skew, kurtosis

with open('final_tree.pkl', 'rb') as f:
    final_tree = pickle.load(f)
use_cols = ['cnum', 'pred', 'vmax', 'vmin', 'vavg']  # , 'emax', 'emin']#, 'l_num', 'r_num', 'm_num']
all_cols = ['cnum', 'pred', 'new', 'vmax', 'vmin', 'vavg', 'appnum', 'emax',
            'emin', 'l_score', 'r_score', 'm_score', 'l_num', 'r_num', 'm_num']

df = pandas.read_csv('../data/test.csv')
submit = pandas.read_csv('model0506/submit.csv')
df['pred'] = submit['is_duplicate'].values

df2 = pandas.read_csv('../data/train.csv')
pos_rate = df2['is_duplicate'].sum() / df2.shape[0]
df2['pred'] = df2['is_duplicate'] / pos_rate * 0.165


import networkx as nx
G = nx.Graph()

#edges = [tuple(x) for x in df[['question1', 'question2', 'pred']].values]
# G.add_weighted_edges_from(edges)
map_score = dict(((x[0], x[1]), x[2]) for x in df[['question1', 'question2', 'pred']].values)

#edges = [tuple(x) for x in df2[['question1', 'question2', 'pred']].values]
# G.add_weighted_edges_from(edges)
map_score2 = dict(((x[0], x[1]), x[2]) for x in df2[['question1', 'question2', 'pred']].values)
map_score.update(map_score2)
edges = [(k[0], k[1], v) for k, v in map_score.items()]
G.add_weighted_edges_from(edges)

import copy
cnt = 0
numpy.random.seed(111)
cliques = sorted(list(nx.find_cliques(G)), key=lambda x: (len(x), max(map(str, x))))

from collections import defaultdict

map_result = copy.deepcopy(map_score)
map_cnum = {}
map_data = {}
map_app = defaultdict(int)

map_max = {}
map_min = {}

for cli in tqdm(cliques):
    # if len(cli) < 2:
    #    continue
    if len(cli) == 1:
        q1 = cli[0]
        print(q1)
        map_result[q1, q1] = 1.
        map_cnum[q1, q1] = 1
        map_data[q1, q1] = (1., 1., 1.)
        continue
    keys = {}
    for q1, q2 in combinations(cli, 2):
        if (q1, q2) in map_result:
            keys[q1, q2] = map_result[q1, q2]
        elif (q2, q1) in map_result:
            keys[q2, q1] = map_result[q2, q1]
        # elif (q1, q2) in map_score2:
        #    keys[q1, q2] = map_score2[q1, q2]
        # elif (q2, q1) in map_score2:
        #    keys[q2, q1] = map_score2[q2, q1]
        else:
            raise Exception('no edge {}'.format((q1, q2)))

    lval = list(keys.values())
    val_max = numpy.max(lval)
    val_min = numpy.min(lval)
    val_avg = numpy.mean(lval)
    """
    val_med = numpy.median(lval)
    val_std = numpy.std(lval)
    val_skew = skew(lval)
    val_kurt = kurtosis(lval)
    """

    if val_avg > 0.4:  # avg_pos:
        val = val_max
        keys = {k: numpy.max([val, map_result[k]]) for k in keys}
    elif val_avg > 0.05:
        val = val_avg
        keys = {k: numpy.max([val, map_result[k]]) for k in keys}
    else:
        val = val_min
        keys = {k: numpy.min([val, map_result[k]]) for k in keys}

    map_result.update(keys)
    keys = {k: len(cli) for k in keys}
    map_cnum.update(keys)
    keys = {k: (val_max, val_min, val_avg) for k in keys}
    map_data.update(keys)
    for k in keys:
        map_app[k] += 1
        map_max[k] = max(val, map_max.get(k, -1))
        map_min[k] = min(val, map_min.get(k, 999))

list_val = []
list_data = []
list_qid = []
for qid, q1, q2 in tqdm(df[['test_id', 'question1', 'question2']].values):
    key = (q1, q2)
    if q1 == q2:
        list_qid.append(qid)
    #    #map_result[key] = 1.
    #    #list_qid.append(qid)
    new_pred = map_result[q1, q2]
    # if key not in map_cnum:
    #    map_cnum[q1, q2] = 0
    #    map_data[q1, q2] = (new_pred, new_pred, new_pred)
    list_val.append(map_result[q1, q2])
    cnum = map_cnum.get((q1, q2), 2)
    data = list(map_data.get((q1, q2), (new_pred, new_pred, new_pred)))
    pred = map_score[key]
    appnum = map_app[key]

    l_num = len(G[key[0]])
    r_num = len(G[key[1]])
    m_num = (l_num + r_num) / 2

    l_score = numpy.mean([map_result[key[0], to] if (key[0], to)
                          in map_result else map_result[to, key[0]] for to in G[key[0]]])
    r_score = numpy.mean([map_result[to, key[1]] if (to, key[1])
                          in map_result else map_result[key[1], to] for to in G[key[1]]])
    m_score = (l_score + r_score) / 2

    emin = map_min.get(key, new_pred)
    emax = map_max.get(key, new_pred)

    #'cnum', 'pred', 'new', 'vmax','vmin', 'vavg'
    list_data.append([cnum, pred, new_pred] + data + [appnum, emax, emin,
                                                      l_score, r_score, m_score, l_num, r_num, m_num])

list_data = pandas.DataFrame(list_data, columns=all_cols)
list_data.to_csv('clique_data_test.csv', index=False)
data = list_data[use_cols].values
if data.shape[1] != final_tree.feature_importances_.shape[0]:
    raise Exception('Not match feature num: %s %s' % (data.shape[1], final_tree.feature_importances_.shape[0]))

pred = final_tree.predict_proba(data)[:, 1]

list_data['last'] = pred
list_data['test_id'] = submit['test_id'].values

submit = pandas.read_csv('submit.csv')
submit['is_duplicate'] = pred  # list_val
submit.loc[submit['test_id'].isin(list_qid), 'is_duplicate'] = 1.
submit.to_csv('submit_clique.csv', index=False)