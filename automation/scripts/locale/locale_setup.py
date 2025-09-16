#---------------------------------------------------------
# Default values
#---------------------------------------------------------
environments = ["dev", "tst", "prd"] # List of environments to setup
action = "create" # Options: create/delete. Defaults to 'create' if not set.
                  
#---------------------------------------------------------
# Main script
#---------------------------------------------------------
import subprocess, os, sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.append(os.getcwd())

import modules.auth_functions as authfunc

for environment in environments: 
    env_credentials = authfunc.get_environment_credentials(environment, os.path.join(os.path.dirname(__file__), f'../../credentials/'))
    script_path = 'fabric_setup.py'

    args = ["--environment", environment, 
            "--action", action,
            "--tenant_id", env_credentials.get("tenant_id"),
            "--client_id", env_credentials.get("client_id"),
            "--client_secret", env_credentials.get("client_secret"),
            "--github_pat", env_credentials.get("github_pat")
            ]

    process = subprocess.Popen(['python', '-u', script_path] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

    # Print the output line by line as it is generated
    for line in process.stdout:
        print(line, end='')  # `end=''` prevents adding extra newlines

    # Optionally, you can also print stderr (errors) as they occur
    for line in process.stderr:
        print(f"Error: {line}", end='')

    # Wait for the process to complete and get the exit code
    process.wait()