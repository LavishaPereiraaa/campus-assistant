"""Chatbot core configuration."""

import os

# Intent confidence thresholds
CONF_HIGH = float(os.getenv("CHATBOT_CONF_HIGH", "0.80"))
CONF_MEDIUM = float(os.getenv("CHATBOT_CONF_MEDIUM", "0.60"))

# For low-confidence intent we must not guess
CONF_MIN = float(os.getenv("CHATBOT_CONF_MIN", "0.65"))

