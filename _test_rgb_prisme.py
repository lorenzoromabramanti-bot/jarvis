# -*- coding: utf-8 -*-
"""Banc : l'autotest de rgb_prisme.py (phrases RGB reconnues, lampes HA ignorées, Prisme absent géré)."""
import os
import runpy

runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rgb_prisme.py"), run_name="__main__")
