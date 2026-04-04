# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division
import logging
import os

LOG_PATH = "/tmp/E2ScreenRecorder.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

log = logging.getLogger("E2ScreenRecorder")
