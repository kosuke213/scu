from pathlib import Path

from scu.config import ImageFormat
from scu.output import FilesystemOutputWriter


def test_filesystem_output_writer_persists_bytes(tmp_path: Path) -> None:
    writer = FilesystemOutputWriter()
    session_dir = tmp_path / "session"

    result = writer.write_capture(
        session_dir=session_dir,
        index=1,
        image_format=ImageFormat.PNG,
        image_bytes=b"payload",
        jpeg_quality=90,
    )

    assert result == session_dir / "page_0001.png"
    assert result.read_bytes() == b"payload"
