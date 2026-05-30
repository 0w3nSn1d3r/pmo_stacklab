import os
from datetime import datetime, timezone
from flask import session
from .config import SESSION_TTL


def step(counts):
    if 'session_id' not in session:
        session['session_id'] = os.urandom(16).hex()

    sid = session['session_id']
    now = datetime.now(timezone.utc)

    # Evict stale sessions
    stale = [k for k, v in counts.items() if now - v['last_seen']
             > SESSION_TTL]
    for k in stale:
        del counts[k]

    if sid not in counts:
        counts[sid] = {'count': 0, 'last_seen': now}

    counts[sid]['count'] += 1
    counts[sid]['last_seen'] = now

    return counts
