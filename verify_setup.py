import sys
import os

# Ensure the parent directory is in the path so we can import 'hana_sentinel'
sys.path.append(os.getcwd())

try:
    print("Verifying imports...")
    from hana_sentinel.adk_app.agents.supervisor import SupervisorAgent
    from hana_sentinel.adk_app.agents.health_agent import HealthAgent
    from hana_sentinel.adk_app.tools.hana_client import HanaClient

    print("Imports successful.")

    # Check if we can instantiate Supervisor (Mocking params might be needed but Supervisor init is mostly lazy or config based)
    # The SupervisorAgent init creates HanaClient which might fail if env vars aren't set or valid, but let's see.
    # We will try-catch the instantiation.
    try:
        agent = SupervisorAgent()
        print("SupervisorAgent instantiated successfully.")
    except Exception as e:
        print(f"SupervisorAgent instantiation failed (expected if config missing): {e}")

except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

print("Verification complete.")
