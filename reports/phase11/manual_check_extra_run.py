"""Runs five new made-up students through the real system and saves the full outputs."""
import json, sys
sys.path.insert(0, r"C:\AL_outcome_predictor")
from src.system import DecisionSupportSystem
from src.models.student import validate

P = {
 "F_agriculture": dict(ol_school_type="Private or semi-government school", g6_11_perf_rating=3, class_rank_freq="Often",
   ol_religion="A", ol_first_language="B", ol_english="B", ol_maths="C", ol_history="B", ol_science="B",
   ol_cat1="B", ol_cat2="A", ol_cat3="C", g11_self_study_hours="11 - 20",
   se1=3, se2=4, se3=3, se4=3, er1=4, er2=4, er3=4, er4=2, int1=4, int2=4, int3=5, int4=3,
   career_goal_clear="Yes", stream_influences=["Personal Interest", "Career Goals"],
   al_subject_combination="Biology + Chemistry + Agri Science", al_district="Anuradhapura",
   al_target_degree="Agriculture or Food Science"),
 "G_high_grades_low_habits": dict(ol_school_type="National school", g6_11_perf_rating=5, class_rank_freq="Always",
   ol_religion="A", ol_first_language="A", ol_english="A", ol_maths="A", ol_history="A", ol_science="A",
   ol_cat1="A", ol_cat2="A", ol_cat3="A", g11_self_study_hours="Less than 5",
   se1=3, se2=3, se3=3, se4=3, er1=2, er2=2, er3=2, er4=4, int1=3, int2=2, int3=3, int4=2,
   career_goal_clear="Not Sure", stream_influences=["Parents"],
   al_subject_combination="Chemistry + Physics + Combined Maths", al_district="Colombo",
   al_target_degree="Engineering"),
 "H_medicine_gap": dict(ol_school_type="Provincial school", g6_11_perf_rating=3, class_rank_freq="Sometimes",
   ol_religion="B", ol_first_language="A", ol_english="C", ol_maths="C", ol_history="B", ol_science="B",
   ol_cat1="B", ol_cat2="C", ol_cat3="B", g11_self_study_hours="5 - 10",
   se1=3, se2=4, se3=3, se4=4, er1=3, er2=4, er3=4, er4=3, int1=4, int2=4, int3=4, int4=3,
   career_goal_clear="Yes", stream_influences=["Personal Interest", "Teachers"],
   al_subject_combination="Biology + Chemistry + Physics", al_district="Matara",
   al_target_degree="Medicine"),
 "I_very_weak": dict(ol_school_type="Other", g6_11_perf_rating=1, class_rank_freq="Never",
   ol_religion="S", ol_first_language="C", ol_english="W", ol_maths="S", ol_history="S", ol_science="S",
   ol_cat1="W", ol_cat2="S", ol_cat3="S", g11_self_study_hours="Less than 5",
   se1=1, se2=2, se3=1, se4=2, er1=2, er2=1, er3=2, er4=5, int1=2, int2=2, int3=3, int4=1,
   career_goal_clear="No", stream_influences=["Friends"],
   al_subject_combination="Biology + Chemistry + Physics", al_district="Kilinochchi",
   al_target_degree="Biological Science"),
 "J_physical_science": dict(ol_school_type="National school", g6_11_perf_rating=4, class_rank_freq="Often",
   ol_religion="A", ol_first_language="A", ol_english="B", ol_maths="A", ol_history="B", ol_science="A",
   ol_cat1="A", ol_cat2="B", ol_cat3="A", g11_self_study_hours="More than 30",
   se1=4, se2=5, se3=4, se4=4, er1=5, er2=4, er3=5, er4=1, int1=5, int2=4, int3=5, int4=5,
   career_goal_clear="Yes", stream_influences=["Personal Interest", "Teachers", "Career Goals"],
   al_subject_combination="Chemistry + Physics + Combined Maths", al_district="Hambantota",
   al_target_degree="Physical Science"),
}
# I2 = I with only O/L Maths and Science improved (direction check)
P["I2_direction_check"] = dict(P["I_very_weak"], ol_maths="B", ol_science="B")

sysm = DecisionSupportSystem.load()
out = {}
for k, p in P.items():
    validate(p, require_gap_fields=True)
    out[k] = {"profile": p, **sysm.report(p)}
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), indent=1, default=str)
print("ok", list(out))
