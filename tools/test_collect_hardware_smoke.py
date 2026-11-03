# SPDX-License-Identifier: MIT
import unittest
from collect_hardware_smoke import cpu_metrics,fields


class SmokeCpuReviewTests(unittest.TestCase):
    def test_steady_work_and_spikes_are_distinguished(self):
        self.assertEqual(cpu_metrics([50]*16),(50.,50.,50,[]))
        self.assertEqual(cpu_metrics([50]*15+[500]),(50.,78.125,500,['peak_spike']))
        self.assertEqual(cpu_metrics([600]*16),(600.,600.,600,['median_budget']))

    def test_incomplete_or_invalid_observations_reject(self):
        for times in ([50]*15,[True]*16,[-1]*16):
            with self.assertRaises(ValueError):cpu_metrics(times)
        with self.assertRaises(ValueError):fields('RNBO_SMOKE CASE id=a id=b','RNBO_SMOKE CASE ')


if __name__=='__main__':unittest.main()
