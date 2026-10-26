import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pregame_evidence import observe_game,collect

G={"event_id":"100","start_utc":"2026-10-30T23:00:00Z","home_team":"KC","away_team":"SEA"}
P={"header":{"competitions":[{"id":"100","competitors":[
{"team":{"abbreviation":"KC"}},{"team":{"abbreviation":"SEA"}}]}]},
"injuries":[{"team":{"abbreviation":"KC"},"injuries":[
{"athlete":{"displayName":"Example Player","position":{"abbreviation":"CB"}},"status":"Questionable"}]}]}
T="2026-10-30T12:00:00Z"
class FakeResponse:
    def raise_for_status(self):pass
    def json(self):return P
class Client:
    def get(self,*args,**kwargs):return FakeResponse()

class PregameEvidenceTests(unittest.TestCase):
    def test_capture_not_confirmed(self):
        x=observe_game(G,P,T)
        self.assertEqual(x["injury_observations"][0]["observations"][0]["position"],"CB")
        self.assertFalse(x["injuries_officially_confirmed"])
        self.assertIsNone(x["candidate_probability_adjustment"])
    def test_reject_post_kickoff(self):
        with self.assertRaises(ValueError):observe_game(G,P,"2026-10-31T00:00:00Z")
    def test_reject_wrong_event(self):
        p=dict(P);p["header"]={"competitions":[{"id":"200"}]}
        with self.assertRaises(ValueError):observe_game(G,p,T)
    def test_collect(self):
        x=collect({"sport":"nfl","events":[G]},session=Client(),observed_at=T)
        self.assertEqual(len(x["games"]),1)
        self.assertFalse(x["impact_model_training_authorized"])
    def test_started_game_not_queried(self):
        x=collect({"sport":"nfl","events":[G]},session=Client(),
                  observed_at="2026-10-31T00:00:00Z")
        self.assertEqual(x["games"][0]["availability"],"started_before_collection")
if __name__=="__main__":unittest.main()
