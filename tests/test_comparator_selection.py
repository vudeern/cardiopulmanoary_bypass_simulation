"""Check frozen selection decisions using deliberately conflicting candidates."""
import unittest
from examples.conservative_study import METRICS, select


class SelectionTests(unittest.TestCase):
    def fixtures(self):
        variants = [dict(id=x, family=f, policy='sentinel', options={}) for x,f in
                    [('guarded','guarded'), ('r1','reserve'), ('r2','reserve'),
                     ('c1','flow_cap'), ('c2','flow_cap')]]
        def row(variant, low, deficit, empty=0.):
            return dict(variant=variant, **{m:({'low_reservoir_s':low,
                'deficit_auc':deficit, 'empty_request_s':empty}.get(m,0.)) for m in METRICS})
        return variants, row

    def test_unsafe_low_deficit_is_not_selected(self):
        variants, row = self.fixtures()
        tuning = [row('guarded',0,10), row('r1',1,0), row('r2',0,5),
                  row('c1',0,8), row('c2',0,3)]
        result = select(tuning, variants)
        self.assertEqual([v['id'] for v in result['selected']], ['r2','c2'])
        self.assertTrue(all(v['matched_tuning_budget'] for v in result['selected']))

    def test_no_match_is_explicit_and_prioritizes_exposure(self):
        variants, row = self.fixtures()
        tuning = [row('guarded',0,10), row('r1',2,0), row('r2',1,100),
                  row('c1',0,5,empty=1), row('c2',1,1)]
        result = select(tuning, variants)
        self.assertEqual([v['id'] for v in result['selected']], ['r2','c1'])
        self.assertTrue(all(not v['matched_tuning_budget'] for v in result['selected']))


if __name__ == '__main__':
    unittest.main()
