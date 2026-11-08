import unittest
import sys
from app.core.config import settings
from app.services.realtime_service import realtime_manager


class TestRedisFreeArchitecture(unittest.IsolatedAsyncioTestCase):
    def test_redis_settings_and_imports_absence(self):
        """Verifies that Redis is strictly not present in settings, services, or modules."""
        self.assertFalse(hasattr(settings, "REDIS_URL"))
        self.assertNotIn("redis", sys.modules.get("app.core.config", {}).__dict__)
        self.assertFalse(hasattr(realtime_manager, "redis"))
        self.assertFalse(hasattr(realtime_manager, "redis_task"))

    def test_realtime_manager_postgres_engine(self):
        """Verifies that the realtime manager relies on database-backed tickets and outbox."""
        self.assertTrue(hasattr(realtime_manager, "start_worker_engine"))
        self.assertTrue(hasattr(realtime_manager, "stop_worker_engine"))
        self.assertTrue(hasattr(realtime_manager, "create_ticket"))
        self.assertTrue(hasattr(realtime_manager, "consume_ticket"))
