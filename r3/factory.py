"""One place that builds a ready-to-use Assistant from whatever data files exist."""
from . import config
from .assistant import Assistant
from .data_loader import load_catalogue, load_policy
from .embedder import get_embedder


def build_assistant():
    cpath, c_mock = config.catalogue_path()
    ppath, p_mock = config.policy_path()
    products, sections = load_catalogue(cpath), load_policy(ppath)
    key = f"{cpath}|{cpath.stat().st_mtime_ns}|{cpath.stat().st_size}"
    a = Assistant(products, sections, get_embedder(), key, is_mock=c_mock or p_mock)
    a.catalogue_file, a.policy_file = str(cpath), str(ppath)
    return a
