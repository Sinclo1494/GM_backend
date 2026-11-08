from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner

runner = DiscoverRunner(verbosity=0)
setup_test_environment()
old_config = runner.setup_databases()
try:
    from django.db import connection
    cur = connection.cursor()
    cur.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_name LIKE '%externalservice%'")
    print("rows:", [(r[0], r[1]) for r in cur.fetchall()])
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()