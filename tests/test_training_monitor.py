import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from sensor_training_data import save_json
from watch_xanhnon_training import snapshot, verified_worker


class TrainingMonitorTests(unittest.TestCase):
    def test_manual_rejection_is_finished_and_does_not_imply_dead_training(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            save_json(root/'sensor-queue.json',{'status':'rejected_answer_review','phase':'manual_review_finished'})
            with patch('watch_xanhnon_training.training_in_progress',return_value=False):
                current=snapshot(root)
            self.assertTrue(current['terminal'])
            self.assertFalse(current['needs_attention'])

    def test_answer_evaluation_is_not_misreported_as_training(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            candidate=root/'candidate'
            review=root/'review-state.json'
            save_json(root/'sensor-queue.json',{'status':'training','candidate':str(candidate),
                'phase':'answer_evaluation','review_state':str(review)})
            save_json(candidate/'progress.json',{'phase':'final_validation','steps_completed':8,'steps_planned':8})
            save_json(review,{'status':'evaluating','phase':'candidate','completed_cases':12})
            with patch('watch_xanhnon_training.training_in_progress',return_value=False):
                current=snapshot(root)
            self.assertEqual(current['phase'],'answer_evaluation')
            self.assertFalse(current['trainer_running'])
            self.assertEqual(current['review_completed_cases'],12)

    def test_current_fourb_job_takes_precedence_over_finished_sensor_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            candidate=root/'fourb-candidate'
            cycle=root/'cycle-state.json'
            save_json(root/'sensor-queue.json',{'status':'awaiting_answer_evaluation','candidate':str(root/'old')})
            save_json(root/'current-training.json',{'cycle_state':str(cycle),'worker_create_time':100.0})
            save_json(cycle,{'status':'running','candidate':str(candidate),'worker_pid':123})
            save_json(candidate/'progress.json',{'phase':'baseline_validation','steps_completed':0,'steps_planned':16})
            with patch('watch_xanhnon_training.training_in_progress',return_value=True):
                current=snapshot(root)
            self.assertEqual(current['candidate'],str(candidate))
            self.assertEqual(current['queue_status'],'training')
            self.assertEqual(current['phase'],'baseline_validation')
            self.assertEqual(current['steps_planned'],16)

    def test_baseline_validation_is_distinct_from_completed_update_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            candidate=root/"candidate"
            save_json(root/"sensor-queue.json",{"status":"training","candidate":str(candidate),"phase":"trainer_starting"})
            save_json(candidate/"progress.json",{"steps_completed":0,"configuration":{"epochs":1,"accumulation":4},
                                                  "data":{"train":{"encoded_rows":150}}})
            with patch("watch_xanhnon_training.training_in_progress",return_value=True):
                current=snapshot(root)
            self.assertEqual(current["phase"],"baseline_validation")
            self.assertEqual(current["steps_planned"],38)

    def test_reused_pid_is_not_reported_as_a_live_worker(self):
        process = Mock()
        process.create_time.return_value = 200.0
        process.is_running.return_value = True
        process.cmdline.return_value = ["python.exe", "queue_sensor_training.py", "--work"]
        with patch("watch_xanhnon_training.psutil.Process", return_value=process):
            self.assertIsNone(verified_worker({"worker_pid": 123, "worker_create_time": 100.0}))
            self.assertIsNotNone(verified_worker({"worker_pid": 123, "worker_create_time": 200.0}))

    def test_recovery_worker_is_verified_without_accepting_unrelated_process(self):
        process = Mock()
        process.create_time.return_value = 200.0
        process.is_running.return_value = True
        job = {"worker_pid": 123, "worker_create_time": 200.0}
        with patch("watch_xanhnon_training.psutil.Process", return_value=process):
            process.cmdline.return_value = ["python.exe", "recover_xanhnon_training.py"]
            self.assertIsNotNone(verified_worker(job))
            process.cmdline.return_value = ["python.exe", "unrelated.py"]
            self.assertIsNone(verified_worker(job))

    def test_recovered_steps_are_not_confused_with_new_training_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            save_json(root / "sensor-queue.json", {"status": "training", "candidate": str(candidate)})
            progress = {"steps_completed": 88, "steps_planned": 168,
                        "recovery": {"checkpoint_step": 88}}
            save_json(candidate / "progress.json", progress)
            with patch("watch_xanhnon_training.training_in_progress", return_value=True):
                self.assertEqual(snapshot(root)["phase"], "checkpoint_validation")
                progress["resume_checkpoint_validation_loss"] = 0.8
                save_json(candidate / "progress.json", progress)
                self.assertEqual(snapshot(root)["phase"], "updating_adapter")

    def test_completion_needs_a_completed_training_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            save_json(root / "sensor-queue.json", {"status": "awaiting_answer_evaluation", "candidate": str(candidate)})
            with patch("watch_xanhnon_training.training_in_progress", return_value=False):
                self.assertTrue(snapshot(root)["needs_attention"])
                save_json(candidate / "training_report.json", {"selected_data_pass_completed": True, "steps": 12, "steps_completed": 12})
                current = snapshot(root)
                self.assertFalse(current["needs_attention"])
                self.assertEqual(current["steps_completed"], 12)

    def test_dead_nonterminal_worker_is_flagged_without_starting_a_trainer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_json(root / "sensor-queue.json", {"status": "preparing_sources"})
            with patch("watch_xanhnon_training.training_in_progress", return_value=False):
                current = snapshot(root)
            self.assertTrue(current["needs_attention"])
            self.assertFalse(current["worker_alive"])


if __name__ == "__main__":
    unittest.main()
