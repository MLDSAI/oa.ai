import pytest
import time
import multiprocessing
from openadapt import record, db, config

@pytest.fixture
def setup_environment():
    # Setup code before the test
    config.RECORD_VIDEO = True
    config.RECORD_IMAGES = True
    config.RECORD_BROWSER_EVENTS = False
    config.RECORD_AUDIO = False
    config.PLOT_PERFORMANCE = False

    yield

    # Teardown code after the test
    db_path = config.RECORDING_DIR_PATH / "recording.db"
    if db_path.exists():
        db_path.unlink()

def test_recording_smoke_test(setup_environment):
    terminate_processing = multiprocessing.Event()
    terminate_recording = multiprocessing.Event()
    status_pipe_parent, status_pipe_child = multiprocessing.Pipe()

    record_process = multiprocessing.Process(
        target=record.record,
        args=("Test Task", terminate_processing, terminate_recording, status_pipe_child)
    )
    record_process.start()

    # Wait for the recording to start
    start_time = time.time()
    while time.time() - start_time < 30:
        if status_pipe_parent.poll():
            message = status_pipe_parent.recv()
            if message.get("type") == "record.started":
                break
        time.sleep(1)
    else:
        pytest.fail("Recording did not start within 30 seconds")

    # Stop the recording by emitting the stop sequence
    terminate_processing.set()
    terminate_recording.wait()

    # Assert the state of the database
    session = db.get_new_session(read_and_write=True)
    recording = db.crud.get_latest_recording(session)
    assert recording is not None, "Recording was not created in the database"

    # Assert the state of the filesystem
    video_file_path = config.RECORDING_DIR_PATH / f"{recording.timestamp}.mp4"
    assert video_file_path.exists(), "Video file was not created"
    performance_plot_path = config.RECORDING_DIR_PATH / f"{recording.timestamp}_performance.png"
    assert performance_plot_path.exists(), "Performance plot was not created"

    record_process.join()
