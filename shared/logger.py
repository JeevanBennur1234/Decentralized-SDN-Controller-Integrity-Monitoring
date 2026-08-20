import logging, json, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_logger(name: str) -> logging.Logger:
    lg = logging.getLogger(name)
    if lg.handlers:
        return lg
    lg.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(name)-20s] %(levelname)s: %(message)s"))
    lg.addHandler(h)
    return lg
