import os


# Ensure a headless Qt backend is used for all test suites, including smoke tests.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
