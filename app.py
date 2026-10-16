"""
Sugar Cosmetics - Instagram Performance Dashboard (Streamlit)
Run:  streamlit run app.py
Needs data/sugar_cosmetics_clean.csv  (created by 01_preprocessing.py)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

st.set_page_config(page_title="Sugar Cosmetics | Instagram Analytics", page_icon="💄", layout="wide")

# ----------------------------------------------------------------- style
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]   # validated categorical order
BLUE, MUTE, GRID = PAL[0], "#52514e", "#e4e3df"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TAGS = ["#BoldLooks", "#CrueltyFree", "#MakeupGoals", "#SugarCosmetics", "#VeganBeauty"]

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1300px;}
[data-testid="stMetric"] {background:#f6f5f2; border-radius:10px; padding:12px 16px;}
[data-testid="stMetricLabel"] p {font-size:.8rem; color:#52514e;}
h1 {font-size:1.7rem !important; margin-bottom:0;}
.callout {border-left:4px solid #2a78d6; background:#f6f5f2; padding:10px 14px; border-radius:0 8px 8px 0; margin:6px 0 14px 0;}
.warn {border-left-color:#eda100;}
.small {color:#52514e; font-size:.85rem;}
</style>""", unsafe_allow_html=True)


def style(fig, h=340, legend=True):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(color=MUTE, size=12), title=dict(font=dict(size=14, color="#0b0b0b"), x=0),
                      showlegend=legend, legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


@st.cache_data
def load():
    d = Path(__file__).parent / "data"
    p = d / "sugar_cosmetics_clean.csv.gz"
    if not p.exists():
        p = d / "sugar_cosmetics_clean.csv"
    if not p.exists():
        st.error("Data file not found in data/ - run `python 01_preprocessing.py` first.")
        st.stop()
    return pd.read_csv(p, parse_dates=["post_date"])


df_all = load()

# ----------------------------------------------------------------- sidebar filters
st.sidebar.header("Filters")
dmin, dmax = df_all.post_date.min().date(), df_all.post_date.max().date()
dr = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
if len(dr) != 2:
    st.sidebar.info("Pick an end date.")
    st.stop()


def ms(label, col):
    opts = sorted(df_all[col].unique())
    return st.sidebar.multiselect(label, opts, default=opts)


f_type = ms("Post type", "post_type")
f_camp = ms("Campaign type", "campaign_type")
f_src = ms("Engagement source", "engagement_source")
f_emo = ms("Audience emotion", "audience_emotion")
f_day = st.sidebar.multiselect("Weekday", DAYS, default=DAYS)
f_tag = st.sidebar.multiselect("Hashtag (post uses ANY selected)", TAGS, default=[],
                               help="Leave empty to include all posts.")
if st.sidebar.button("Reset filters"):
    st.rerun()

df = df_all[(df_all.post_date.dt.date >= dr[0]) & (df_all.post_date.dt.date <= dr[1]) &
            df_all.post_type.isin(f_type) & df_all.campaign_type.isin(f_camp) &
            df_all.engagement_source.isin(f_src) & df_all.audience_emotion.isin(f_emo) & df_all.weekday.isin(f_day)]
if f_tag:
    m = np.zeros(len(df), dtype=bool)
    for t in f_tag:
        m |= df["has_" + t.lstrip("#").lower()].values
    df = df[m]

st.sidebar.markdown(f"**{len(df):,}** of {len(df_all):,} posts selected")
st.sidebar.caption("Engagement rate = (likes + comments + shares + saves) / reach")

if df.empty:
    st.title("Instagram Performance - Sugar Cosmetics")
    st.warning("No posts match these filters.")
    st.stop()

# ----------------------------------------------------------------- header + KPIs
st.title("Instagram Performance Analytics - Sugar Cosmetics")
st.caption(f"{df.post_date.min():%d %b %Y} to {df.post_date.max():%d %b %Y}  |  {len(df):,} posts")

wer = df.total_interactions.sum() / df.reach.sum() * 100
k = st.columns(6)
k[0].metric("Posts", f"{len(df):,}")
k[1].metric("Total reach", f"{df.reach.sum()/1e6:,.1f}M")
k[2].metric("Total likes", f"{df.likes.sum()/1e6:,.1f}M")
k[3].metric("Total comments", f"{df.comments.sum()/1e6:,.2f}M")
k[4].metric("Avg eng. rate", f"{df.engagement_rate.mean():.2f}%", help="Mean of per-post (likes+comments+shares+saves)/reach")
k[5].metric("New follows", f"{df.follows.sum()/1e6:,.2f}M")
k = st.columns(6)
k[0].metric("Impressions", f"{df.impressions.sum()/1e6:,.0f}M")
k[1].metric("Avg reach / post", f"{df.reach.mean():,.0f}")
k[2].metric("Shares", f"{df.shares.sum()/1e6:,.2f}M")
k[3].metric("Saves", f"{df.saves.sum()/1e6:,.2f}M")
k[4].metric("Profile visits", f"{df.profile_visits.sum()/1e6:,.1f}M")
k[5].metric("Follow conv.", f"{df.follows.sum()/df.profile_visits.sum()*100:.1f}%", help="Follows / profile visits")

tabs = st.tabs(["Overview", "Content performance", "Timing", "Hashtags", "Funnel & growth", "Top posts", "Insights & recommendations"])

# ----------------------------------------------------------------- 1. overview
with tabs[0]:
    mo = df.groupby(["year_month", "partial_month"]).agg(posts=("post_id", "size"), er=("engagement_rate", "mean"),
                                                        reach=("reach", "mean")).reset_index()
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Scatter(x=mo.year_month, y=mo.posts, mode="lines+markers", line=dict(color=BLUE, width=2),
                                   marker=dict(size=8, color=np.where(mo.partial_month, PAL[3], BLUE)),
                                   hovertemplate="%{x}<br>%{y:,} posts<extra></extra>"))
        fig.update_layout(title="Posts per month")
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(style(fig, legend=False), width="stretch")
        st.caption("Yellow markers = partial months (data starts and ends on the 19th), so they look low by construction.")
    with c2:
        fig = go.Figure(go.Scatter(x=mo.year_month, y=mo.er, mode="lines+markers", line=dict(color=PAL[2], width=2),
                                   marker=dict(size=8), hovertemplate="%{x}<br>%{y:.2f}% avg ER<extra></extra>"))
        fig.update_layout(title="Average engagement rate % by month")
        fig.update_yaxes(range=[0, max(25, mo.er.max() * 1.2)])
        st.plotly_chart(style(fig, legend=False), width="stretch")
        st.caption("Y-axis starts at zero on purpose: month-to-month movement is small.")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(df, x="engagement_rate", nbins=40, color_discrete_sequence=[BLUE])
        fig.update_layout(title="Distribution of post engagement rates", xaxis_title="engagement rate %", yaxis_title="posts")
        st.plotly_chart(style(fig, legend=False), width="stretch")
    with c2:
        g = df.groupby("post_type").size().reset_index(name="posts")
        fig = px.bar(g, x="post_type", y="posts", color="post_type", color_discrete_sequence=PAL)
        fig.update_layout(title="Posts by type", xaxis_title="", yaxis_title="")
        st.plotly_chart(style(fig, legend=False), width="stretch")

# ----------------------------------------------------------------- 2. content
with tabs[1]:
    dim_label = {"post_type": "Post type", "campaign_type": "Campaign type",
                 "engagement_source": "Engagement source", "audience_emotion": "Audience emotion"}
    dim = st.radio("Compare by", list(dim_label), format_func=dim_label.get, horizontal=True)
    g = df.groupby(dim).agg(posts=("post_id", "size"), likes=("likes", "mean"), comments=("comments", "mean"),
                            shares=("shares", "mean"), saves=("saves", "mean"), reach=("reach", "mean"),
                            er=("engagement_rate", "mean")).reset_index().sort_values("er", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(g, x=dim, y="er", text=g.er.round(2), color_discrete_sequence=[BLUE])
        fig.update_traces(textposition="outside", hovertemplate="%{x}<br>%{y:.2f}% ER<extra></extra>")
        fig.update_layout(title="Avg engagement rate % (axis from zero)", xaxis_title="", yaxis_title="")
        fig.update_yaxes(range=[0, g.er.max() * 1.18])
        st.plotly_chart(style(fig, legend=False), width="stretch")
    with c2:
        long = g.melt(id_vars=dim, value_vars=["likes", "comments", "shares", "saves"], var_name="metric", value_name="avg")
        fig = px.bar(long[long.metric != "likes"], x=dim, y="avg", color="metric", barmode="group",
                     color_discrete_sequence=[PAL[1], PAL[2], PAL[3]])
        fig.update_layout(title="Avg comments, shares, saves per post", xaxis_title="", yaxis_title="")
        st.plotly_chart(style(fig), width="stretch")
    fig = px.bar(g, x=dim, y="likes", text=g.likes.round(0), color_discrete_sequence=[PAL[4]])
    fig.update_traces(textposition="outside", texttemplate="%{y:,.0f}")
    fig.update_layout(title="Avg likes per post", xaxis_title="", yaxis_title="")
    fig.update_yaxes(range=[0, g.likes.max() * 1.18])
    st.plotly_chart(style(fig, 300, legend=False), width="stretch")

    # significance
    if df[dim].nunique() > 1 and len(df) > 50:
        grp = [x.engagement_rate.values for _, x in df.groupby(dim) if len(x) > 1]
        p = stats.f_oneway(*grp).pvalue if len(grp) > 1 else np.nan
        gap = g.er.max() - g.er.min()
        verdict = ("is statistically significant" if p < 0.05 else "is NOT statistically significant - treat the ranking as noise")
        st.markdown(f"<div class='callout {'warn' if p >= .05 else ''}'><b>Is the difference real?</b> Best vs worst "
                    f"{dim_label[dim].lower()} differ by <b>{gap:.2f} percentage points</b> of engagement rate "
                    f"(ANOVA p = {p:.3f}) - this {verdict}.</div>", unsafe_allow_html=True)
    st.dataframe(g.rename(columns={"er": "avg ER %"}).round(2), width="stretch", hide_index=True)

    pv = df.pivot_table(index="post_type", columns="campaign_type", values="engagement_rate").round(2)
    fig = px.imshow(pv, text_auto=".2f", color_continuous_scale=["#eaf1fb", BLUE], aspect="auto")
    fig.update_layout(title="Avg engagement rate % - post type x campaign", coloraxis_showscale=False)
    st.plotly_chart(style(fig, 300, legend=False), width="stretch")

# ----------------------------------------------------------------- 3. timing
with tabs[2]:
    wd = df.groupby("weekday").agg(posts=("post_id", "size"), er=("engagement_rate", "mean"), likes=("likes", "mean"),
                                   reach=("reach", "mean")).reindex(DAYS).reset_index()
    metric = st.radio("Metric", ["Engagement rate %", "Avg likes", "Avg reach"], horizontal=True)
    col = {"Engagement rate %": "er", "Avg likes": "likes", "Avg reach": "reach"}[metric]
    best = wd.loc[wd[col].idxmax(), "weekday"]
    fig = px.bar(wd, x="weekday", y=col, text=wd[col].round(2 if col == "er" else 0), color_discrete_sequence=[BLUE])
    fig.update_traces(marker_color=[PAL[1] if d == best else BLUE for d in wd.weekday], textposition="outside")
    fig.update_layout(title=f"{metric} by weekday (best day highlighted)", xaxis_title="", yaxis_title="")
    fig.update_yaxes(range=[0, wd[col].max() * 1.18])
    st.plotly_chart(style(fig, legend=False), width="stretch")
    gap = (wd[col].max() - wd[col].min()) / wd[col].mean() * 100
    st.markdown(f"<div class='callout warn'>Best vs worst weekday differ by only <b>{gap:.1f}%</b> (relative) on this metric. "
                f"Weekday is a weak lever in this dataset.</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        hm = df.pivot_table(index="weekday", columns="month_label", values="engagement_rate", aggfunc="mean").reindex(DAYS)
        order = df.sort_values("post_date").month_label.unique()
        hm = hm[[c for c in order if c in hm.columns]]
        fig = px.imshow(hm.round(1), text_auto=".1f", color_continuous_scale=["#eaf1fb", BLUE], aspect="auto")
        fig.update_layout(title="Avg ER % - weekday x month", coloraxis_showscale=False)
        st.plotly_chart(style(fig, 360, legend=False), width="stretch")
    with c2:
        q = df.groupby("quarter").agg(er=("engagement_rate", "mean"), posts=("post_id", "size")).reset_index()
        fig = px.bar(q, x="quarter", y="er", text=q.er.round(2), color_discrete_sequence=[PAL[2]])
        fig.update_traces(textposition="outside")
        fig.update_layout(title="Avg ER % by quarter", xaxis_title="", yaxis_title="")
        fig.update_yaxes(range=[0, q.er.max() * 1.2])
        st.plotly_chart(style(fig, 360, legend=False), width="stretch")

# ----------------------------------------------------------------- 4. hashtags
with tabs[3]:
    rows = []
    for t in TAGS:
        c = "has_" + t.lstrip("#").lower()
        a = df[df[c]]
        if len(a):
            rows.append({"hashtag": t, "posts": len(a), "avg_er": a.engagement_rate.mean(), "avg_reach": a.reach.mean(),
                         "avg_likes": a.likes.mean(), "avg_saves": a.saves.mean()})
    ht = pd.DataFrame(rows).sort_values("avg_er", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(ht.sort_values("posts"), x="posts", y="hashtag", orientation="h", color_discrete_sequence=[BLUE])
        fig.update_layout(title="Most-used hashtags (posts)", xaxis_title="", yaxis_title="")
        st.plotly_chart(style(fig, 320, legend=False), width="stretch")
    with c2:
        fig = px.bar(ht.sort_values("avg_er"), x="avg_er", y="hashtag", orientation="h", text=ht.sort_values("avg_er").avg_er.round(2),
                     color_discrete_sequence=[PAL[2]])
        fig.update_traces(textposition="outside")
        fig.update_layout(title="Avg engagement rate % when hashtag is used", xaxis_title="", yaxis_title="")
        fig.update_xaxes(range=[0, ht.avg_er.max() * 1.15])
        st.plotly_chart(style(fig, 320, legend=False), width="stretch")
    combo = df.groupby("hashtag_combo").agg(posts=("post_id", "size"), er=("engagement_rate", "mean"),
                                           reach=("reach", "mean"), saves=("saves", "mean")).reset_index()
    combo = combo[combo.posts >= 30].sort_values("er", ascending=False)
    c1, c2 = st.columns([3, 2])
    with c1:
        top = pd.concat([combo.head(8), combo.tail(5)]).drop_duplicates().sort_values("er")
        fig = px.bar(top, x="er", y="hashtag_combo", orientation="h", text=top.er.round(2), color_discrete_sequence=[BLUE])
        fig.update_traces(textposition="outside")
        fig.update_layout(title="Hashtag combinations: top 8 and bottom 5 by avg ER %", xaxis_title="", yaxis_title="")
        fig.update_xaxes(range=[0, top.er.max() * 1.15])
        st.plotly_chart(style(fig, 440, legend=False), width="stretch")
    with c2:
        n = df.groupby("hashtag_count").agg(er=("engagement_rate", "mean"), sem=("engagement_rate", "sem")).reset_index()
        fig = go.Figure(go.Bar(x=n.hashtag_count.astype(str), y=n.er, error_y=dict(type="data", array=1.96 * n["sem"]),
                               marker_color=PAL[3], text=n.er.round(2), textposition="outside"))
        fig.update_layout(title="Avg ER % by number of hashtags (95% CI)", xaxis_title="hashtags used", yaxis_title="")
        fig.update_yaxes(range=[0, n.er.max() * 1.2])
        st.plotly_chart(style(fig, 440, legend=False), width="stretch")
    st.markdown("<div class='callout warn'>Single hashtags barely differ. Combinations show a small but statistically detectable spread "
                "on the full dataset (~0.8 pp), so use them as A/B test candidates, not proven rules. Small filtered slices will be noisy.</div>",
                unsafe_allow_html=True)

# ----------------------------------------------------------------- 5. funnel & growth
with tabs[4]:
    stages = ["impressions", "reach", "likes", "comments", "shares", "saves"]
    tot = df[stages].sum()
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure(go.Funnel(y=[s.title() for s in stages], x=tot.values, text=[f"{v/1e6:,.1f}M" for v in tot.values], textinfo="text+percent initial",
                                  marker=dict(color=[BLUE, PAL[2], PAL[3], PAL[1], PAL[4], "#6250d6"])))
        fig.update_layout(title="Engagement funnel: impressions to saves")
        st.plotly_chart(style(fig, 420, legend=False), width="stretch")
    with c2:
        steps = pd.DataFrame({"stage": [s.title() for s in stages], "total": tot.values})
        steps["% of impressions"] = (steps.total / steps.total.iloc[0] * 100).round(2)
        steps["% of reach"] = [np.nan] + list((steps.total.iloc[1:] / steps.total.iloc[1] * 100).round(2))
        steps["total"] = steps.total.map("{:,.0f}".format)
        steps["% of reach"] = steps["% of reach"].map(lambda v: "-" if pd.isna(v) else f"{v:.2f}")
        steps["% of impressions"] = steps["% of impressions"].map("{:.2f}".format)
        st.dataframe(steps, width="stretch", hide_index=True)
        st.caption("Likes, comments, shares and saves are separate actions (one person can do several), so this is a "
                   "funnel of volumes, not a strict one-way path.")
    st.subheader("Profile visits and follower growth")
    c1, c2 = st.columns(2)
    with c1:
        gm = df.groupby("year_month").agg(visits=("profile_visits", "sum"), follows=("follows", "sum"), posts=("post_id", "size")).reset_index()
        gm["follows_per_post"] = gm.follows / gm.posts
        fig = go.Figure(go.Scatter(x=gm.year_month, y=gm.follows_per_post, mode="lines+markers", line=dict(color=BLUE, width=2)))
        fig.update_layout(title="New follows per post, by month")
        fig.update_yaxes(range=[0, gm.follows_per_post.max() * 1.25])
        st.plotly_chart(style(fig, legend=False), width="stretch")
    with c2:
        samp = df.sample(min(len(df), 4000), random_state=1)
        fig = px.scatter(samp, x="profile_visits", y="follows", opacity=.35, color_discrete_sequence=[PAL[2]])
        fig.update_layout(title="Profile visits vs follows (4,000-post sample)")
        st.plotly_chart(style(fig, legend=False), width="stretch")
    c1, c2, c3 = st.columns(3)
    c1.metric("Profile visits per 100 reached", f"{df.profile_visits.sum()/df.reach.sum()*100:.1f}")
    c2.metric("Follows per 1,000 reached", f"{df.follows.sum()/df.reach.sum()*1000:.1f}")
    c3.metric("Avg views per reached account", f"{df.impressions.sum()/df.reach.sum():.2f}")
    st.markdown("<div class='callout'>Engagement <i>rate</i> is independent of reach in this data (correlation ~0), but likes and follows "
                "scale with reach and follows track profile visits strongly (r = 0.84). More reach = more outcomes.</div>",
                unsafe_allow_html=True)

# ----------------------------------------------------------------- 6. top posts
with tabs[5]:
    cols = ["post_id", "post_date", "post_type", "campaign_type", "engagement_source", "hashtags", "reach", "likes", "comments",
            "shares", "saves", "engagement_rate"]
    st.caption("The dataset has no caption text, so posts are identified by ID, date, type and hashtags.")
    c1, c2 = st.columns(2)
    for col, key, title in [(c1, "likes", "Top 10 by likes"), (c2, "engagement_rate", "Top 10 by engagement rate")]:
        t = df.nlargest(10, key)[cols].copy()
        t["label"] = t.post_id + " | " + t.post_type
        with col:
            fig = px.bar(t.iloc[::-1], x=key, y="label", orientation="h", color_discrete_sequence=[BLUE if key == "likes" else PAL[2]],
                         text=t.iloc[::-1][key].round(1 if key == "engagement_rate" else 0))
            fig.update_traces(textposition="outside")
            fig.update_layout(title=title, xaxis_title="", yaxis_title="")
            fig.update_xaxes(range=[0, t[key].max() * 1.15])
            st.plotly_chart(style(fig, 380, legend=False), width="stretch")
            st.dataframe(t.drop(columns="label").assign(post_date=t.post_date.dt.date).round(2), width="stretch", hide_index=True)
    st.markdown("<div class='callout'>Top-likes posts are essentially the highest-reach posts. Top-engagement-rate posts include ordinary-reach "
                "posts that over-index on interactions - the 'hidden gems'.</div>", unsafe_allow_html=True)
    st.download_button("Download filtered data (CSV)", df[cols].to_csv(index=False), "filtered_posts.csv", "text/csv")

# ----------------------------------------------------------------- 7. insights
with tabs[6]:
    st.subheader("Does anything actually move engagement? (live test on your current filters)")
    rows = []
    for c, lbl in [("post_type", "Post type"), ("campaign_type", "Campaign type"), ("engagement_source", "Engagement source"),
                   ("audience_emotion", "Audience emotion"), ("weekday", "Weekday"), ("hashtag_count", "Number of hashtags"),
                   ("hashtag_combo", "Hashtag combination")]:
        grp = [x.engagement_rate.values for _, x in df.groupby(c) if len(x) > 1]
        if len(grp) > 1:
            g = df.groupby(c).engagement_rate.mean()
            p = stats.f_oneway(*grp).pvalue
            rows.append({"Factor": lbl, "Best level": str(g.idxmax()), "Best ER %": round(g.max(), 2), "Worst ER %": round(g.min(), 2),
                         "Gap (pp)": round(g.max() - g.min(), 2), "p-value": round(p, 4), "Significant?": "Yes" if p < .05 else "No"})
    if rows:
        st.dataframe(pd.DataFrame(rows).sort_values("p-value"), width="stretch", hide_index=True)
    st.caption("With 25 hashtag combinations tested, one 'significant' result at p<0.05 can arise by chance; confirm with an A/B test.")

    st.subheader("Key insights (full dataset)")
    st.markdown("""
1. **Large scale, flat trajectory.** 50,000 posts reached ~987M accounts at an 18.5% average engagement rate and brought in ~8.9M follows. Posting volume (~4,100-4,300 a month), engagement rate and reach are essentially flat across the year: consistent, not growing.
2. **No content format is a clear winner.** Reels, Stories, Videos and Images sit within 0.2 pp of each other (p = 0.15). The same holds for campaign type, audience emotion, engagement source and weekday (all p > 0.3).
3. **Paid is not outperforming organic.** Paid posts have no engagement-rate advantage (p = 0.36) and slightly *lower* average reach (about -1.8%, p = 0.014). Question the paid ROI.
4. **Hashtag combinations are the only detectable lever, and a weak one.** `#BoldLooks + #CrueltyFree + #MakeupGoals` averages ~19.0% ER against ~18.2% for the weakest combination, and also has the highest average saves (and a top-4 average reach). Posts with 2 hashtags edge out 1 (borderline).
5. **Reach drives volume.** Engagement rate does not rise with reach, but likes and follows scale with it. Follows track profile visits (r = 0.84): ~3 in 100 reached people visit the profile, and ~30% of visitors follow.
6. **The funnel leaks after the like.** About 15% of reached accounts like, but only ~1.9% comment, ~0.8% share and ~0.9% save. Shares and saves are the signals that spread content and show lasting value.
""")
    st.subheader("Recommendations")
    st.markdown("""
| Area | Recommendation | Why (evidence) |
|---|---|---|
| **Format & timing** | Stop optimising around a "best day" or format; keep a balanced mix and use the calendar for campaign needs, not engagement gains. | All gaps under 0.3 pp and not significant. |
| **Hashtags** | A/B test `#BoldLooks + #CrueltyFree + #MakeupGoals` (and 2-3 tag sets) vs the current mix for 4 weeks. Avoid single-tag posts. | Best combo ~+0.8 pp over the worst; 2-tag posts beat 1-tag. |
| **Paid budget** | Audit paid spend; shift part of it to creator/collab and organic experiments and compare cost per follower. | Paid reach slightly below organic, no ER lift. |
| **Growth** | Put effort into reach: collabs, shareable formats, trend-led Reels. Add stronger profile CTAs and link-in-bio hooks. | Outcomes scale with reach; follows track profile visits. |
| **Depth of engagement** | Add share/save triggers (tutorial carousels, "save this routine", shade guides, giveaways that require a share). | Comments, shares, saves are the thinnest funnel steps. |
| **Experimentation** | Introduce planned tests (one variable at a time) since observed differences are tiny. Track follows per 1,000 reached as a north-star alongside ER. | Flat account; no existing variation to exploit. |
| **Data** | Capture captions, posting time, creator ID, and spend so content themes and ROI can be analysed. | Caption and cost fields are missing from the export. |
""")
    st.subheader("Campaign ideas aligned with the brand")
    st.markdown("""
- **"Vegan + Cruelty-free" series** built around the winning hashtag cluster, as a tutorial carousel set designed for saves.
- **Share-to-win giveaway** to lift shares, currently the weakest step.
- **Creator collab Reels** with a clear profile-visit hook ("full shade list on our profile").
- **Festive and launch bursts** with a test/control split (hashtag set A vs B) to turn the calendar into an experiment.
""")
    st.markdown("<div class='callout warn'><b>Caveats.</b> No caption field in the file; Apr 2024 and Apr 2025 are partial months; "
                "engagement rates are almost uniformly distributed, which is unusual for real Instagram data, so these findings describe this "
                "dataset and should be confirmed on live account analytics.</div>", unsafe_allow_html=True)
