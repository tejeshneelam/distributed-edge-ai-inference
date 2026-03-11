"""
services/__init__.py — Application-level service singletons.

Import from here to ensure all routes share the same instances.
"""

from backend.services.worker_manager import WorkerManager
from backend.services.result_aggregator import ResultAggregator
from backend.services.metrics_service import MetricsService
from backend.services.frame_distributor import FrameDistributor
from backend.services.frame_queue import FrameQueue
from backend.services.job_tracker import JobTracker
from backend.services.inference_service import InferenceService

worker_manager = WorkerManager()
result_aggregator = ResultAggregator(worker_manager)
metrics_service = MetricsService(worker_manager, result_aggregator)
frame_distributor = FrameDistributor()
inference_service = InferenceService()
frame_queue = FrameQueue(worker_manager, result_aggregator, inference_service)
job_tracker = JobTracker()
# Give metrics_service access to queue stats (avoids circular import at module level)
metrics_service.set_frame_queue(frame_queue)
