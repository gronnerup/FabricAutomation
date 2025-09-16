#---------------------------------------------------------
# Default values
#---------------------------------------------------------
environments = "dev,tst" # List of environments to include in parameter file
                    
#---------------------------------------------------------
# Main script
#---------------------------------------------------------
import subprocess, os, sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.append(os.getcwd())

import modules.auth_functions as authfunc

env_credentials = authfunc.get_environment_credentials(None, os.path.join(os.path.dirname(__file__), f'../../credentials/'))
script_path = 'utils_build_parameter_file.py'

args = ["--environments", environments, 
        "--tenant_id", env_credentials.get("tenant_id"),
        "--client_id", env_credentials.get("client_id"),
        "--client_secret", env_credentials.get("client_secret")
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