"""Scientific and malformed-input regression checks; synthetic fixtures are tests only."""
from pathlib import Path
import hashlib
import math
import sys
import tempfile
import unittest

import pandas as pd

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from src.log_parser import parse_logs,FIELDS,GROUPS
from src.data_audit import audit
from src.statistics import with_derived,describe,compute_statistics
from run import validate_output


def line(frame=10,**changes):
    values=dict(mode='online',frame=frame,raw=100,candidate_hits=5,mask_voxels=2,callback_ms=1.25,
                learning_frames=frame-1,orientation_bins=3,candidate_voxels=7,dropped_learning_batches=0)
    values.update(changes)
    return ' '.join(f'{k}={v}' for k,v in values.items())


class ParserChecks(unittest.TestCase):
    def parse(self,text,encoding='utf-8'):
        # Temporary fixtures remain inside visualization/, never beside real logs.
        with tempfile.TemporaryDirectory(dir=PROJECT/'tests') as temp:
            p=Path(temp)/'01_static.log'
            p.write_bytes(text.encode(encoding))
            before=hashlib.sha256(p.read_bytes()).hexdigest()
            result=parse_logs(temp)
            self.assertEqual(before,hashlib.sha256(p.read_bytes()).hexdigest())
            return result

    def test_ros_prefix_spacing_and_delimiters(self):
        text='[INFO] [1.2] [gasf]: '+line().replace('=', ' = ')+'\r\n---\r\n\n'
        r=self.parse(text)
        self.assertEqual(len(r.records),1)
        self.assertEqual(r.records.frame.iloc[0],10)
        self.assertEqual(r.records.callback_ms.iloc[0],1.25)
        self.assertEqual(str(r.records.frame.dtype),'Int64')
        self.assertEqual(r.inventory.separator_lines.iloc[0],1)

    def test_missing_is_not_zero(self):
        r=self.parse(line().replace('mask_voxels=2',''))
        self.assertTrue(pd.isna(r.records.mask_voxels.iloc[0]))
        self.assertIn('missing_field',r.diagnostics.code.tolist())

    def test_invalid_values_and_overflow(self):
        r=self.parse(line(callback_ms='NaN',raw=-1,candidate_hits='1.2',frame=2**63))
        self.assertEqual(r.records[['frame','raw','candidate_hits','callback_ms']].isna().sum().sum(),4)
        self.assertFalse(r.records.analysis_eligible.iloc[0])

    def test_duplicate_key_is_ambiguous(self):
        r=self.parse(line()+' raw=200')
        self.assertTrue(pd.isna(r.records.raw.iloc[0]))
        self.assertIn('duplicate_field',r.diagnostics.code.tolist())

    def test_duplicate_frames_are_retained_but_excluded(self):
        r=self.parse(line()+'\n'+line())
        self.assertEqual(len(r.records),2)
        self.assertFalse(r.records.analysis_eligible.any())
        self.assertEqual((r.diagnostics.code=='duplicate_frame').sum(),2)

    def test_restart_is_not_sorted_away(self):
        r=self.parse(line(20)+'\n'+line(10))
        self.assertEqual(r.records.frame.tolist(),[20,10])
        self.assertFalse(r.records.analysis_eligible.any())
        self.assertIn('frame_reversal',r.diagnostics.code.tolist())

    def test_gap_reported_without_fabrication(self):
        r=self.parse(line(10)+'\n'+line(30))
        self.assertEqual(r.records.frame.tolist(),[10,30])
        self.assertIn('irregular_frame_interval',r.diagnostics.code.tolist())

    def test_unknown_line_reported(self):
        r=self.parse('broken record here\n'+line())
        self.assertIn('unrecognized_line',r.diagnostics.code.tolist())
        self.assertEqual(len(r.records),1)

    def test_bad_encoding_is_explicit(self):
        with tempfile.TemporaryDirectory(dir=PROJECT/'tests') as temp:
            (Path(temp)/'01_static.log').write_bytes(b'\x80\x81')
            r=parse_logs(temp)
            self.assertIn('decode_error',r.diagnostics.code.tolist())

    def test_bom_utf16(self):
        r=self.parse(line(),encoding='utf-16')
        self.assertEqual(r.records.raw.iloc[0],100)

    def test_zero_and_excessive_ratios(self):
        r=self.parse(line(raw=0)+'\n'+line(20,raw=10,candidate_hits=12))
        d=with_derived(r.records)
        self.assertTrue(pd.isna(d.mask_hit_ratio.iloc[0]))
        self.assertEqual(d.mask_hit_ratio.iloc[1],1.2)
        self.assertIn('hits_exceed_raw',r.diagnostics.code.tolist())

    def test_empty_input_yields_diagnostics_not_crash(self):
        with tempfile.TemporaryDirectory(dir=PROJECT/'tests') as temp:
            r=parse_logs(temp)
            self.assertEqual((r.diagnostics.code=='missing_group').sum(),7)
            self.assertEqual(len(audit(r)['data_quality']),7)
            self.assertEqual(len(compute_statistics(with_derived(r.records))['callback_latency_summary']),7)


class StatisticsChecks(unittest.TestCase):
    def test_known_linear_quantiles(self):
        summary=describe(pd.Series([0.,10.,20.,30.]))
        self.assertEqual(summary['p50'],15.)
        self.assertAlmostEqual(summary['p95'],28.5)
        self.assertAlmostEqual(summary['p99'],29.7)
        self.assertEqual(summary['n_valid'],4)

    def test_undefined_constant_correlation(self):
        with tempfile.TemporaryDirectory(dir=PROJECT/'tests') as temp:
            (Path(temp)/'01_static.log').write_text(line(mask_voxels=0)+'\n'+line(20,mask_voxels=0),encoding='utf-8')
            s=compute_statistics(with_derived(parse_logs(temp).records))['orientation_association']
            self.assertTrue(pd.isna(s.loc[(s.group=='01_static')&(s.target=='mask_voxels'),'spearman_rho'].iloc[0]))

    def test_ratio_weights_are_distinct(self):
        with tempfile.TemporaryDirectory(dir=PROJECT/'tests') as temp:
            (Path(temp)/'01_static.log').write_text(line(raw=10,candidate_hits=5)+'\n'+line(20,raw=100,candidate_hits=0),encoding='utf-8')
            s=compute_statistics(with_derived(parse_logs(temp).records))['mask_hit_ratio_summary'].iloc[0]
            self.assertEqual(s['mean'],.25)
            self.assertAlmostEqual(s.pooled_logged_points_ratio,5/110)


class RepositoryChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=PROJECT.parent/'analysis/results/online_controls'
        cls.result=parse_logs(cls.root)

    def test_all_real_values_against_independent_token_reader(self):
        r=self.result
        self.assertEqual(len(r.records),845)
        self.assertEqual(len(r.diagnostics),0)
        for g,n in zip(GROUPS,[64,63,177,174,71,177,119]):
            raw=[dict(token.split('=',1) for token in text.split())
                 for text in (self.root/f'{g}.log').read_text(encoding='utf-8').splitlines() if text.startswith('mode=')]
            parsed=r.records[r.records.group==g]
            self.assertEqual(len(raw),n)
            for original,(_,row) in zip(raw,parsed.iterrows()):
                for field in FIELDS:
                    expected=float(original[field]) if field=='callback_ms' else int(original[field])
                    self.assertEqual(row[field],expected)

    def test_real_activation_and_retained_maximum(self):
        s=compute_statistics(with_derived(self.result.records))
        act=s['mask_activation_summary'].set_index('group')
        for g,frame in [('03_arc_A',170),('04_loop_A',140),('06_arc_B',170),('07_loop_B',50)]:
            self.assertEqual(act.loc[g,'first_positive_sample_frame'],frame)
        self.assertEqual(s['callback_latency_summary'].maximum.max(),9.304)

    def test_output_cannot_overlap_input_or_sources(self):
        with self.assertRaises(ValueError):
            validate_output(self.root,self.root)
        with self.assertRaises(ValueError):
            validate_output(self.root,PROJECT/'src')
        with self.assertRaises(ValueError):
            validate_output(PROJECT/'logs',PROJECT)
        validate_output(self.root,PROJECT/'rerun')


if __name__=='__main__':
    unittest.main()
