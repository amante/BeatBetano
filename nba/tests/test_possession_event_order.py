import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_possessions import order_referenced_misses


class EventOrderTests(unittest.TestCase):
    def test_reorders_only_referenced_same_clock_misses_without_live_intervening_action(self):
        context = {'period': 2, 'clock': 'PT05M15.00S', 'scoreHome': '30', 'scoreAway': '25'}
        rebound = dict(context, actionNumber=3, actionType='rebound', shotActionNumber=2)
        miss = dict(context, actionNumber=2, actionType='2pt', shotResult='Missed')
        block = dict(context, actionNumber=4, actionType='block')
        actions = [rebound, block, miss]
        order_referenced_misses(actions)
        self.assertEqual([event['actionNumber'] for event in actions], [2, 3, 4])
        for actions in ([rebound, dict(miss, scoreHome='31')],
                        [rebound, dict(block, actionType='substitution'), miss]):
            original = list(actions)
            order_referenced_misses(actions)
            self.assertEqual(actions, original)
