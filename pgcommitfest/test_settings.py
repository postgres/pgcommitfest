"""Test settings for pgcommitfest."""

from pgcommitfest.settings import *  # noqa: F403

# Disable automatic creation of commitfests during tests
# Tests should explicitly create the commitfests they need
AUTO_CREATE_COMMITFESTS = False
