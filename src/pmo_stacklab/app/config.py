
# Time before session vars are cleared
from datetime import timedelta
SESSION_TTL = timedelta(hours=2)

# Ordered pipeline of first-order Process instances, as configured by the user.
# Placeholder until the generic Process class + registry are in place; the
# generalized /api/execute endpoint will index this list by pipeline step.
ORDER = []

