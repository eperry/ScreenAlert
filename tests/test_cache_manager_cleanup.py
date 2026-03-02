from pathlib import Path

from PIL import Image

from screenalert_core.core.cache_manager import CacheManager


def test_cleanup_temp_files_removes_old_files(tmp_path: Path):
    manager = CacheManager(lifetime_seconds=1.0)

    old_file = tmp_path / "old.tmp"
    old_file.write_text("x")

    removed = manager.cleanup_temp_files(str(tmp_path), max_age_seconds=0)
    assert removed >= 1
    assert not old_file.exists()


def test_cache_invalidate_all():
    manager = CacheManager(lifetime_seconds=100.0)
    image = Image.new("RGB", (10, 10), color=(10, 20, 30))
    manager.set(123, image)
    assert manager.get(123) is not None
    manager.invalidate_all()
    assert manager.get(123) is None
