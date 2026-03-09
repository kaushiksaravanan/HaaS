import sys
sys.path.insert(0, '.')
# Import just hana_tools without the full adk_app package
import importlib.util
spec = importlib.util.spec_from_file_location("hana_tools", "adk_app/tools/hana_tools.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("Import OK")

# Test check_hana_connection
result = mod.check_hana_connection()
print("check_hana_connection:", result)

# Test query_hana
result2 = mod.query_hana("SELECT 1 AS test FROM DUMMY")
print("query_hana:", result2)
