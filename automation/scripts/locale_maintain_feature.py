#---------------------------------------------------------
# Default values
#---------------------------------------------------------
branch_name = "feature/MyFeature" # Full name of branch, e.g. "feature/MyFeatureBranch"
action = "create" # Options: create/delete. Defaults to 'create' if not set.

#---------------------------------------------------------
# Main script
#---------------------------------------------------------
import subprocess, os
import modules.auth_functions as authfunc

env_credentials = authfunc.get_environment_credentials("dev", os.path.join(os.path.dirname(__file__), f'../../credentials/'))
script_path = 'automation/scripts/fabric_feature_maintainance.py'

args = ["--tenant_id", env_credentials.get("tenant_id"),
        "--client_id", env_credentials.get("client_id"),
        "--client_secret", env_credentials.get("client_secret"),
        "--action", action,
        "--branch_name", branch_name,]

process = subprocess.Popen(['python', script_path] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Print the output line by line as it is generated
for line in process.stdout:
    print(line, end='')  # `end=''` prevents adding extra newlines

# Optionally, you can also print stderr (errors) as they occur
for line in process.stderr:
    print(f"Error: {line}", end='')

# Wait for the process to complete and get the exit code
process.wait()