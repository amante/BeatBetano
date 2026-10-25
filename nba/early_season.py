"""Early-season experimental sample-shrinkage rule; does not change production.

Previously chosen hard switch n<3 uses Elo only. Alternative blends
Challenger signal gradually; requires prospective evaluation before promotion.
"""
def shrinkage(elo_p_home,challenger_p_home,n_home,n_away,full_sample=10):
    if not all(0<=p<=1 for p in (elo_p_home,challenger_p_home)):
        raise ValueError("Probabilities outside [0,1]")
    if min(n_home,n_away)<0 or full_sample<1:
        raise ValueError("Invalid sample sizes")
    weight=min(1.0,min(n_home,n_away)/full_sample)
    return {"candidate_p_home":elo_p_home+weight*(challenger_p_home-elo_p_home),
            "sample_weight":weight,"experimental":True,
            "production_approved":False}

