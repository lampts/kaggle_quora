from itertools import combinations
from tqdm import tqdm
import pickle
import pandas
import numpy
import community

from scipy.stats import skew, kurtosis

with open('final_tree.pkl', 'rb') as f:
    final_tree = pickle.load(f)
use_cols = ['cnum', 'pred', 'vmax', 'vmin', 'vavg']  # , 'emax', 'emin']#, 'l_num', 'r_num', 'm_num']

all_cols = ['cnum', 'pred', 'new', 'vmax', 'vmin', 'vavg', 'appnum', 'emax', 'emin', 'l_score',
            'r_score', 'm_score', 'l_num', 'r_num', 'm_num', 'l_min', 'l_max', 'r_min', 'r_max',
            # 'vmed', 'vstd', 'vskew', 'vkurt',
            #'l_med', 'l_std', 'l_skew', 'l_kurt',
            #'r_med', 'r_std', 'r_skew', 'r_kurt'
            'l_cnum_max', 'r_cnum_max', 'l_cnum_min', 'r_cnum_min', 'l_cnum_avg', 'r_cnum_avg',
            'l_eign_cent', 'r_eign_cent'
            ]

df = pandas.read_csv('../data/test.csv')
submit = pandas.read_csv('submit.csv')
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

cluster = {}
cl = community.best_partition(G)
#cl = nx.clustering(G)
for node, c in cl.items():
    c = int(c)
    if c in cluster:
        cluster[c].append(node)
    else:
        cluster[c] = [node]
cliques = sorted(cluster.values(), key=lambda x: (len(x), max(map(str, x))))


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
        q1 = list(cli)[0]
        print(q1)
        map_result[q1, q1] = 1.
        map_cnum[q1, q1] = 1
        map_data[q1, q1] = (1., 1., 1.)
        continue
    keys = {}
    for q1, q2 in combinations(cli, 2):
        if (q1, q2) in map_score:
            keys[q1, q2] = map_score[q1, q2]
        elif (q2, q1) in map_score:
            keys[q2, q1] = map_score[q2, q1]

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
    keys = {k: (val_max, val_min, val_avg  # , val_med, val_std, val_skew, val_kurt
                ) for k in keys}

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
    new_pred = map_score[q1, q2]

    cnum = map_cnum.get((q1, q2), 2)
    data = list(map_data.get((q1, q2), (new_pred, new_pred, new_pred)))
    pred = map_score[key]
    appnum = map_app.get(key, -100)

    l_num = len(G[key[0]])
    r_num = len(G[key[1]])
    m_num = (l_num + r_num) / 2

    l_scores = [map_score[key[0], to] if (key[0], to)
                in map_score else map_score[to, key[0]] for to in G[key[0]]]
    r_scores = [map_score[to, key[1]] if (to, key[1])
                in map_score else map_score[key[1], to] for to in G[key[1]]]
    l_score = numpy.mean(l_scores)
    r_score = numpy.mean(r_scores)
    m_score = (l_score + r_score) / 2

    l_min = numpy.min(l_scores)
    l_max = numpy.max(l_scores)
    r_min = numpy.min(r_scores)
    r_max = numpy.max(r_scores)
    """
    l_med = numpy.median(l_scores)
    l_std = numpy.std(l_scores)
    l_skew = skew(l_scores)
    l_kurt = kurtosis(l_scores)

    r_med = numpy.median(r_scores)
    r_std = numpy.std(r_scores)
    r_skew = skew(r_scores)
    r_kurt = kurtosis(r_scores)
    """
    l_cnums = [map_cnum.get((key[0], to), 1) for to in G[key[0]]]
    r_cnums = [map_cnum.get((to, key[1]), 1) for to in G[key[1]]]

    l_cnum_max = numpy.max(l_cnums)
    r_cnum_max = numpy.max(r_cnums)
    l_cnum_min = numpy.min(l_cnums)
    r_cnum_min = numpy.min(r_cnums)
    l_cnum_avg = numpy.mean(l_cnums)
    r_cnum_avg = numpy.mean(r_cnums)

    l_eign_cent = 0
    r_eign_cent = 0

    emin = map_min.get(key, new_pred)
    emax = map_max.get(key, new_pred)

    #'cnum', 'pred', 'new', 'vmax','vmin', 'vavg'
    list_data.append([cnum, pred, new_pred] + data + [appnum, emax,
                                                      emin, l_score, r_score, m_score, l_num, r_num, m_num,
                                                      l_min, l_max, r_min, r_max,
                                                      #l_med, l_std, l_skew, l_kurt,
                                                      #r_med, r_std, r_skew, r_kurt
                                                      l_cnum_max, r_cnum_max, l_cnum_min, r_cnum_min, l_cnum_avg, r_cnum_avg,
                                                      l_eign_cent, r_eign_cent
                                                      ])


list_data = pandas.DataFrame(list_data, columns=all_cols)
list_data.to_csv('cluster_data_test_0512.csv', index=False)