# SPDX-License-Identifier: MIT
"""Shutdown regressions using fake compiler processes and a fake USB bridge."""
import importlib.util
from pathlib import Path
import signal
import threading
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'rnbo_studio_server_review', Path(__file__).with_name('server.py'))
studio_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(studio_server)


class FakeBridge:
    def __init__(self, events=None):
        self.events = events if events is not None else []

    def disconnect(self):
        self.events.append('disconnect')


class FakeStream:
    def __init__(self, broken=False):
        self.broken = broken
        self.closed = False

    def __iter__(self):
        if self.broken:
            raise RuntimeError('compiler stream failed')
        return iter(())

    def close(self):
        self.closed = True


class ExitedLeader:
    """An exited group leader can still have compiler descendants alive."""
    pid = 912345

    def __init__(self, events=None, broken_stream=False):
        self.events = events if events is not None else []
        self.stdout = FakeStream(broken_stream)
        self.wait_count = 0

    def poll(self):
        return 0

    def wait(self, timeout=None):
        self.events.append('reap')
        self.wait_count += 1
        return 0


class ShutdownReviewTests(unittest.TestCase):
    def test_execute_cleans_descendants_even_after_leader_exit_or_stream_error(self):
        for broken in (False, True):
            with self.subTest(broken_stream=broken):
                studio = studio_server.Studio(bridge=FakeBridge())
                identity = 'a' * 32
                studio.jobs[identity] = {'log': ''}
                process = ExitedLeader(broken_stream=broken)
                with patch.object(studio_server.subprocess, 'Popen', return_value=process), \
                     patch.object(studio_server.os, 'killpg') as kill_group, \
                     patch.object(studio_server.threading, 'Timer') as timer:
                    if broken:
                        with self.assertRaisesRegex(RuntimeError, 'compiler stream failed'):
                            studio.execute(identity, ['fake-compiler'])
                    else:
                        studio.execute(identity, ['fake-compiler'])
                    kill_group.assert_called_with(process.pid, signal.SIGKILL)
                    timer.return_value.cancel.assert_called_once()
                self.assertTrue(process.stdout.closed)
                self.assertGreaterEqual(process.wait_count, 1)
                self.assertIsNone(studio.active_process)

    def test_close_reaps_exited_build_group_and_joins_before_disconnect(self):
        events = []
        studio = studio_server.Studio(bridge=FakeBridge(events))
        process = ExitedLeader(events)
        studio.active_process = process

        class Worker:
            def join(self):
                events.append('join')

        studio.job_thread = Worker()
        with patch.object(studio_server.os, 'killpg',
                          side_effect=lambda *_args: events.append('kill')) as kill_group:
            studio.close()
        kill_group.assert_called_once_with(process.pid, signal.SIGKILL)
        self.assertEqual(events, ['kill', 'reap', 'join', 'disconnect'])
        self.assertTrue(studio.stopping.is_set())

    def test_shutdown_waits_for_existing_flash_without_killing_its_process_group(self):
        entered = threading.Event()
        release = threading.Event()
        join_reached = threading.Event()
        events = []

        class FlashBridge(FakeBridge):
            def flash(self, *_args, **_kwargs):
                events.append('flash-start')
                entered.set()
                if not release.wait(3):
                    raise RuntimeError('test did not release the fake flash')
                events.append('flash-finish')

        studio = studio_server.Studio(bridge=FlashBridge(events))
        identity = 'b' * 32
        studio.jobs[identity] = {
            'id': identity, 'state': 'ready', 'stage': 'Ready', 'log': '',
            'result': {'board': 'xiao', 'kind': 'player'}, '_settings': {'board': 'xiao'},
            '_build': Path('/fake-compiled-build')}
        studio.start_upload({'id': identity, 'port': 'fake-port'})
        self.assertTrue(entered.wait(1))
        worker = studio.job_thread
        original_join = worker.join
        close_errors = []

        def join_upload():
            join_reached.set()
            original_join()

        def close_studio():
            try:
                studio.close()
            except BaseException as error:
                close_errors.append(error)

        closer = threading.Thread(target=close_studio)
        try:
            with patch.object(worker, 'join', side_effect=join_upload), \
                 patch.object(studio_server.os, 'killpg') as kill_group:
                closer.start()
                self.assertTrue(join_reached.wait(1))
                self.assertNotIn('disconnect', events)
                self.assertTrue(studio.worker.locked())
                kill_group.assert_not_called()
                release.set()
                closer.join(2)
                self.assertFalse(closer.is_alive())
            self.assertEqual(close_errors, [])
            self.assertEqual(events, ['flash-start', 'flash-finish', 'disconnect'])
            self.assertEqual(studio.job(identity)['state'], 'done')
            self.assertFalse(studio.worker.locked())
        finally:
            release.set()
            if closer.ident is not None:
                closer.join(3)
            original_join(3)

    def test_closed_studio_rejects_new_build_upload_and_process_launch(self):
        studio = studio_server.Studio(bridge=FakeBridge())
        studio.close()
        with self.assertRaisesRegex(ValueError, 'shutting down'):
            studio.start_build({'patch': {'patcher': {}}})
        with self.assertRaisesRegex(ValueError, 'shutting down'):
            studio.start_upload({'id': 'c' * 32})
        identity = 'd' * 32
        studio.jobs[identity] = {'log': ''}
        with patch.object(studio_server.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(RuntimeError, 'shutting down'):
                studio.execute(identity, ['fake-compiler'])
            launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
