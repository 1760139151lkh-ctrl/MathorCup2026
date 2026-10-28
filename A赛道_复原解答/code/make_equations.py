# -*- coding: utf-8 -*-
"""把论文中的公式渲染为高质量 PNG（matplotlib mathtext，无外部 LaTeX 依赖）。

公式按编号（如 2-1）索引；build_paper.py 按编号读取 figures/equations/eq_<编号>.png。
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels as L

sys.stdout.reconfigure(encoding="utf-8")
OUT = L.FIGURES / "equations"
OUT.mkdir(parents=True, exist_ok=True)

EQ = {
    "2-1": r"$h(q)=q\ (q>0);\quad h(q)=m/2\ (q\leq 0);\quad z=\log_{10}h(q)$",
    "2-2": r"$z=\dfrac{g-\mu}{s}\ \ \Longrightarrow\ \ z'=\dfrac{(a+bg)-(a+b\mu)}{bs}=z$",
    "2-3": r"$10^{d_{37}}=0.0003\,u_{27}+0.4\,u_{31}+0.4\,u_{33}+5.523\,u_{34}+0.4\,u_{36}$",
    "2-4": r"$10^{d_{228}}=u_{6}/23+u_{7}/1.035+u_{8}/0.225+u_{9}/0.1+u_{10}/0.75+u_{11}/10+u_{16}/0.6+u_{19}/1.29$",
    "2-5": r"$10^{d_{229}}=u_{164}/0.625+u_{118}/1.5+u_{155}/0.23+u_{121}/0.0245+u_{128}/0.023+u_{95}/0.0045$",
    "2-6": r"$10^{d_{230}}=u_{23}/0.145+u_{27}/400$",
    "2-7": r"$10^{d_{231}}=u_{2}/50+u_{3}/1.2+u_{4}/19+u_{12}/3.5+u_{22}/11$",
    "2-8": r"$\tilde{x}_j=\dfrac{\mathrm{clip}\left(\mathrm{fill}(x_j,m_j),\,a_j,\,b_j\right)-\mu_j}{s_j}$",
    "3-1": r"$L(B)=\|Y-XB\|_F^2+\lambda\|B\|_F^2$",
    "3-2": r"$\mathrm{NMSE}=\dfrac{1}{50}\sum_{j=1}^{50}\mathrm{mean}_i\left[\dfrac{(Y_{ij}-\hat{Y}_{ij})^2}{(s_j^{\mathrm{train}})^2}\right]$",
    "3-3": r"$\mathrm{rank}=\left\lceil(n_{\mathrm{cal}}+1)\times 0.9\right\rceil=\left\lceil 51\times0.9\right\rceil=46$",
    "3-4": r"$r_i^{\max}=\max_j\dfrac{\left|z_{ij}-\hat{y}_j(x_i)\right|}{s_j^{\mathrm{train}}}$",
    "3-5": r"$G_j(z)=\mathrm{clip}\left(\left\lfloor 3+\dfrac{z-\mu_j}{s_j}+0.5\right\rfloor,\ 0,\ 6\right)$",
    "3-6": r"$G_j^{B}(z)=\sum_{r=1}^{6}\mathbf{1}\{z\geq q_{jr}\},\qquad q_{jr}=\mathrm{quantile}_{r/7}(Y_j)$",
    "4-1": r"$A_{jk}=\left|\rho_{jk}\right|\cdot\mathbf{1}\{|\rho_{jk}|\geq0.6\},\qquad A_{jj}=0$",
    "4-2": r"$Q=\dfrac{1}{2m}\sum_{j,k}\left[A_{jk}-\dfrac{k_jk_k}{2m}\right]\mathbf{1}\{c_j=c_k\}$",
    "4-3": r"$S_{jk}=\left|\mathrm{corr}\!\left(\mathrm{rank}(X_j),\ \mathrm{rank}(Y_k)\right)\right|$",
    "4-4": r"$B=(Z_X^{\top}Z_X+100\,I)^{-1}Z_X^{\top}Z_Y,\qquad \mathrm{score}_{jk}=|B_{jk}|$",
    "4-5": r"$\eta^2_{\mathrm{adj}}=\max\left\{0,\ 1-(1-\eta^2)\dfrac{n-1}{n-G}\right\},\qquad \eta^2=\dfrac{\sum_{g} n_g(\bar z_g-\bar z)^2}{\sum_{i}(z_i-\bar z)^2}$",
    "4-6": r"$R_{jk}=\dfrac{1}{3}\left[\mathrm{rank}_S(j,k)+\mathrm{rank}_B(j,k)+\mathrm{rank}_\eta(j,k)\right]$",
    "4-7": r"$y=a+b\,(x/t)+c\,\max(x/t-1,\ 0)+\varepsilon$",
    "5-1": r"$\tilde{\mu}_c=\dfrac{n_c}{n_c+5}\,\mu_c+\dfrac{5}{n_c+5}\,\mu_{\mathrm{global}}$",
    "5-2": r"$\hat{\Sigma}=(1-\lambda)\,S+\lambda\,\bar{v}\,I$",
    "5-3": r"$\tilde{F}_{jc}(x)=\dfrac{n_{jc}}{n_{jc}+5}\,\hat{F}_{jc}(x)+\dfrac{5}{n_{jc}+5}\,\hat{F}_{j0}(x)$",
    "5-4": r"$x^{\mathrm{prop}}=x^{\mathrm{src}}+\left(\mu_{\mathrm{Tripel}}-\mu_{\mathrm{Pils/Lager}}\right)$",
    "5-5": r"$\min_{x}\ \dfrac{1}{2}\sum_{j}\left[\dfrac{x_j-x_j^{\mathrm{prop}}}{s_j}\right]^2\quad \mathrm{s.t.}\ \ x_j^{C}\leq x_j^{C,\mathrm{src}},\ \ \hat{y}_{38}(x)\leq \hat{y}_{38}(x^{\mathrm{src}}),\ \ \mathrm{agg}(x)>0$",
    "5-6": r"$\mathrm{cap}_i=\min\left\{\hat{y}_{38}(x_i^{\mathrm{orig}}),\ \hat{y}_{38}(x_i^{\mathrm{re}}),\ z_i^{\mathrm{obs}}\right\}$",
    "5-7": r"$x(m)=\mathrm{clip}\left(p-m\,s^2\circ\beta,\ \mathrm{low},\ \mathrm{high}\right),\qquad \beta^{\top}x(m)\leq \mathrm{rhs}$",
    "5-8": r"$F_Q(t)\geq F_S(t)\qquad \mathrm{for\ all}\ t$",
    "5-9": r"$W_1(Q,R)\geq\int\left[F_S(t)-F_R(t)\right]_{+}\,\mathrm{d}t$",
}

manifest = {}
for key, tex in EQ.items():
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=13, color="black")
    path = OUT / f"eq_{key}.png"
    fig.savefig(path, dpi=420, transparent=True, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    # 读取 PNG 尺寸换算自然宽度（cm）
    from PIL import Image
    with Image.open(path) as im:
        w_px, h_px = im.size
    w_cm = w_px / 420 * 2.54
    h_cm = h_px / 420 * 2.54
    manifest[key] = {"file": str(path.name), "width_cm": round(w_cm, 2), "height_cm": round(h_cm, 2)}
    print(f"{key}: {w_cm:.2f}x{h_cm:.2f} cm")

(OUT.parent / "_equation_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("equations:", len(manifest))
