from alembic import context

from app import models  # noqa: F401  (import registers the tables on Base)
from app.db import Base, engine

# ponytail: online mode only. We never generate SQL scripts offline.
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,  # sqlite (tests) can't ALTER in place
    )
    with context.begin_transaction():
        context.run_migrations()
