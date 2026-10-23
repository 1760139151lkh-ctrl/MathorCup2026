# -*- coding: utf-8 -*-
"""22_inversion_validation.py —— 验证 0–6 等级反演方法的有效性（仿真实验）
思路：模拟"16 名品评员对 250 款啤酒按 0–6 打分 → 逐人品评员 z 化 → 取均值"的完整流程，
      再用与问题 1 相同的反演模型恢复等级，统计恢复精度。用于论文中说明反演的可靠性。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
plt = setup_cn_font()

rng = np.random.default_rng(2026)


def simulate_panel(n_beer=250, n_taster=16, n_attr=50, noise=0.8, seed=0):
    """返回 (Y_obs, X_true_grade)，Y_obs 为逐人品评员 z 化后的均值。"""
    r = np.random.default_rng(seed)
    Xgrade = np.zeros((n_beer, n_attr), dtype=int)
    Y = np.zeros((n_beer, n_attr))
    for a in range(n_attr):
        # 等级分布：以 0.35 概率低等级（缺陷类），否则为中等强度
        kind = r.random()
        if kind < 0.35:
            p = np.array([0.45, 0.3, 0.12, 0.06, 0.04, 0.02, 0.01])
        elif kind < 0.8:
            p = np.array([0.08, 0.2, 0.3, 0.24, 0.12, 0.05, 0.01])
        else:
            p = np.array([0.03, 0.08, 0.17, 0.28, 0.25, 0.13, 0.06])
        p = p / p.sum()
        g = r.choice(7, size=n_beer, p=p)
        Xgrade[:, a] = g
        # 品评员效应：个体偏置 + 敏感度
        bias = r.normal(0, 0.45, n_taster)
        sens = r.uniform(1.1, 2.0, n_taster)
        Z = np.zeros((n_beer, n_taster))
        for t in range(n_taster):
            e = g + bias[t] + sens[t] * (g - g.mean()) * 0 + r.normal(0, noise, n_beer)
            e = np.clip(np.round(e), 0, 6)
            mu, sd = e.mean(), e.std()
            if sd < 1e-6:
                sd = 1.0
            Z[:, t] = (e - mu) / sd
        Y[:, a] = Z.mean(axis=1)
    return Y, Xgrade


rows = []
for seed in range(6):
    for n_taster, noise in [(16, 0.8), (10, 1.0)]:
        Ysim, Gtrue = simulate_panel(n_taster=n_taster, noise=noise, seed=seed)
        acc, w1, mae, rho = [], [], [], []
        for a in range(Ysim.shape[1]):
            fit = fit_ordinal_inversion(Ysim[:, a])
            ghat = fit['grade']
            acc.append(np.mean(ghat == Gtrue[:, a]))
            w1.append(np.mean(np.abs(ghat - Gtrue[:, a]) <= 1))
            mae.append(np.mean(np.abs(ghat - Gtrue[:, a])))
        rows.append({'seed': seed, 'n_taster': n_taster, 'noise': noise,
                     'exact': float(np.mean(acc)), 'within1': float(np.mean(w1)),
                     'MAE': float(np.mean(mae))})
    log('seed %2d 完成' % seed)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(RES, 'Q1_inversion_simulation.csv'), index=False, encoding='utf-8-sig')
summ = df.groupby(['n_taster', 'noise'])[['exact', 'within1', 'MAE']].agg(['mean', 'std'])
log(summ.to_string())
log('\n总体：完全一致 %.3f±%.3f，±1 以内 %.3f±%.3f，MAE %.3f'
    % (df['exact'].mean(), df['exact'].std(), df['within1'].mean(),
       df['within1'].std(), df['MAE'].mean()))

# 图：仿真 vs 真实数据反演的一致性
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
ax = axes[0]
for key, sub in df.groupby('n_taster'):
    ax.scatter(sub['exact'], sub['within1'], s=22, label='品评员 %d 人' % key)
ax.set_xlabel('等级完全一致率'); ax.set_ylabel('±1 级以内一致率')
ax.set_title('(a) 仿真实验的等级恢复精度'); ax.legend(frameon=False, fontsize=8)
ax = axes[1]
# 真实数据：逐维度的"反演可辨识度"——等级数与非零权重数
rep = json.load(open(os.path.join(RES, '20_data_report.json'), encoding='utf-8'))
fits = rep['ordinal_fits']
nlev = [int(np.sum(np.array(f['w']) > 0.02)) for f in fits.values()]
bvals = [f['b'] for f in fits.values()]
ax.scatter(nlev, bvals, s=24, color='#4C72B0')
ax.set_xlabel('有效等级数（权重>0.02）'); ax.set_ylabel('等级步长 b')
ax.set_title('(b) 50 个感官维度的反演参数')
fig.suptitle('图 6  0–6 等级反演方法的仿真验证', y=1.02)
savefig(fig, 'fig_q1_inversion_validation.png'); plt.close(fig)
log('Saved figure')
