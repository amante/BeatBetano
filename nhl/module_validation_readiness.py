"""Evidence gates for progressive NHL module validation.

A module is not 'validated' because current-day source coverage exists.
Point-in-time historical inputs and outcome labels are required.
"""
import json
from pathlib import Path

MODULES={
 "crs":{"features":["dated_roster","injury_status","player_deployment"],"target":"ml"},
 "unit_ratings":{"features":["dated_lines","toi","player_metrics"],"target":"ml"},
 "goalie_daily":{"features":["confirmed_starter","goalie_recent_form","rest"],"target":"ml"},
 "special_teams":{"features":["dated_pp","dated_pk","opponent_strength"],"target":"ml"},
 "context":{"features":["home_ice","travel","rest_days","officials"],"target":"ml"},
 "team_rating":{"features":["point_in_time_team_metrics"],"target":"ml"},
 "division_rivalry":{"features":["division","rivalry_registry","historical_context"],"target":"ml"},
 "goal_process_rt":{"features":["regulation_final_goals"],"target":"regulation"},
 "three_goal_lead":{"features":["chronological_goal_events"],"target":"path_3goal"},
 "first_to_three_goal_lead":{"features":["chronological_goal_events"],"target":"path_3goal"},
 "rescue_probability":{"features":["chronological_goal_events","score_state"],"target":"path_rescue"},
 "fuertes_dual":{"features":["joint_model_probabilities","validated_thresholds"],"target":"ml"},
 "return_injury":{"features":["historical_injury_report","return_to_form"],"target":"ml"},
 "opponent_style":{"features":["dated_shot_quality","matchup_context"],"target":"ml"}
}
# What the completed game schedule collector actually provides:
AVAILABLE={"date","game_id","home_team","away_team","final_goals","game_winner"}
def report():
    return {"evidence_source":"NHL weekly completed-games schedule",
      "available_historical_fields":sorted(AVAILABLE),
      "module_validation":{name:{"required_features":data["features"],
       "validation_target":data["target"],"historically_validatable":False,
       "missing_features":data["features"],"status":"blocked_missing_point_in_time_features"}
       for name,data in MODULES.items()},
      "ml_goals_only":{"historically_validatable":True,
          "status":"research_validation_only",
          "features":["historical_prior_final_goals","home_away","date"]},
      "do_not_promote":True}
def main():
    path=Path("results/nhl/module_validation_readiness.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report(),indent=2))
    print(f"Module readiness: {len(MODULES)} guarded; point-in-time data still needed.")
if __name__=="__main__":main()
