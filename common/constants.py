# common/constants.py

import uuid

# Fixed, well-known UUID for the platform's revenue account — not randomly
# generated, so it's the same value in every environment (dev, test, prod)
# and can be referenced directly in code, migrations, and settings without
# needing a lookup-by-name or a runtime query at import time.
PLATFORM_REVENUE_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
