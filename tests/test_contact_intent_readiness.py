"""Exercise real C488/C491 function bodies without importing Blender's bpy.

Only scene lookup and the delegated motor controller are doubles. Certificate
updates and authority decisions use the actual implementation. Not physics proof.
"""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest

from blender import iss_battle_runtime_engagement_authority_v2 as authority
from blender import iss_battle_runtime_certified_alignment_ownership_v1 as alignment
from blender.iss_battle_runtime_autonomy import AutonomyMemory, AutonomyObservation, ClosedLoopGoalController
from blender.iss_battle_runtime_contact_commit_v2 import capability_motion_realization_floor_mps
from blender.iss_battle_runtime_progress_contract_v1 import progress_epsilon_m

ROOT = Path(__file__).resolve().parents[1]


def load_function(path, name, namespace):
    module = ast.parse((ROOT / path).read_text())
    node = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name)
    unit = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(unit), str(path), 'exec'), namespace)
    return namespace[name]


class IntentReadinessContract(unittest.TestCase):
    def test_goal_context_preserves_event_intent_separately_from_readiness(self):
        context = {}
        ns = {'candidate487': SimpleNamespace(
            actual_goal_lifecycle_goal_for_tactical=lambda *args: 'goal',
            _current_frame=lambda event: 10), '_contact_context': context}
        goal = load_function('blender/run_generic_battle_runtime_v1_candidate488_generic_battle.py',
                             'c488_goal_for_tactical', ns)
        actor = SimpleNamespace(profile=SimpleNamespace(entity_id='source'))
        target = SimpleNamespace(profile=SimpleNamespace(entity_id='target'))
        for required in (True, False):
            goal(actor, target, SimpleNamespace(event_id='event', requires_contact=required),
                 SimpleNamespace(mode='ENGAGE', contact_commit=False), {})
            self.assertEqual(context[('event', 'source', 'target')]['requiresContact'], required)
            self.assertFalse(context[('event', 'source', 'target')]['contactCommit'])

    def exercise(self, mode='ENGAGE', requires_contact=True, recovery=False, separating=False, length=4.0):
        key = ('arbitrary-event', 'arbitrary-source', 'arbitrary-target')
        gap = 0.5 if separating else 0.01
        cert = authority.ApproachMotionCertificate(qualified=True, qualified_frame=5, last_effective_gap_m=0.1)
        markers, delegated = [], []
        ns491 = {**vars(alignment), '_active_key': lambda: key,
                 '_alignment_hold_active': {key}, '_certificate_hold_rows': [],
                 '_ORIGINAL_UPDATE_APPROACH_CERTIFICATE': authority.update_approach_certificate,
                 'marker': lambda name, **kw: markers.append((name, kw)), 'MECHANISM': 'test'}
        update = load_function('blender/run_generic_battle_runtime_v1_candidate491_generic_battle.py',
                               'c491_update_approach_certificate', ns491)
        def base(memory, obs, **kw):
            delegated.append(obs)
            return 'BASE'
        ns = {**vars(authority), 'replace': replace,
              '_transaction_key_from_pair': lambda: key,
              'candidate474': SimpleNamespace(_active_pair_context={'effectiveCollisionProxyGapM': gap}),
              '_contact_context': {key: {'frame': 10, 'tacticalMode': mode,
                                        'requiresContact': requires_contact, 'contactCommit': False}},
              '_certificates': {key: cert}, 'ClosedLoopGoalController': ClosedLoopGoalController,
              'capability_motion_realization_floor_mps': capability_motion_realization_floor_mps,
              'progress_epsilon_m': progress_epsilon_m, 'update_approach_certificate': update,
              '_mark_certificate': lambda *a, **kw: None, '_BASE_AUTONOMY_UPDATE': base}
        function = load_function('blender/run_generic_battle_runtime_v1_candidate488_generic_battle.py',
                                 'certified_event_scoped_autonomy_update', ns)
        obs = AutonomyObservation(10, 30, 1.0, gap, 0.71, 2.0, -1.0 if separating else 1.0,
                                  0.0, 0, 0, False, False, True, 18.0, 4.0, 1.0, 3.0, 5.0, 1.0, length)
        memory = AutonomyMemory(mode='RECOVER_TURN' if recovery else 'TRACK')
        self.assertEqual(function(memory, obs), 'BASE')
        return cert, markers, delegated, obs

    def test_alignment_hold_preserves_intent_across_profile_dimensions(self):
        for mode in ('ENGAGE', 'COUNTER'):
            for length in (1.0, 4.0, 12.0):
                with self.subTest(mode=mode, length=length):
                    cert, markers, _, _ = self.exercise(mode=mode, length=length)
                    self.assertTrue(cert.qualified)
                    self.assertIn('G04_CERTIFIED_APPROACH_ALIGNMENT_HOLD', [m[0] for m in markers])

    def test_unready_delegation_cannot_request_base_contact_handoff(self):
        _, _, delegated, original = self.exercise()
        self.assertFalse(delegated[0].requires_contact)
        self.assertTrue(original.requires_contact)

    def test_noncontact_recovery_and_real_separation_still_invalidate(self):
        for kwargs in ({'mode': 'HOLD'}, {'requires_contact': False}, {'recovery': True}, {'separating': True}):
            with self.subTest(kwargs=kwargs):
                cert, _, _, _ = self.exercise(**kwargs)
                self.assertFalse(cert.qualified)


if __name__ == '__main__':
    unittest.main()
