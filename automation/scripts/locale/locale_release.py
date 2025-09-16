#---------------------------------------------------------
# Default values
#---------------------------------------------------------
environments = ["tst"] # Name of environments to release.
layers = "core,ingest,store,prepare,orchestrate,model,insight" # Comma seperated list of layers to deploy. Can also be single layer.
item_types = "Notebook,DataPipeline,Lakehouse,SQLDatabase" # Comma seperated list of item types in scope. Must match Fabric ItemTypes exactly.
unpublish_items = True # Whether to unpublish orphan items that are no longer in the repository. Default is True.
#---------------------------------------------------------
# Main script
#---------------------------------------------------------
import subprocess, os, sys
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.append(os.getcwd())

import modules.auth_functions as authfunc

for environment in environments:
    env_credentials = authfunc.get_environment_credentials(environment, os.path.join(os.path.dirname(__file__), f'../../credentials/'))
    script_path = 'fabric_release.py'

    args = ["--environment", environment, 
            "--layers", layers,
            "--item_types", item_types,
            "--repo_path", os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../solution/')),
            "--unpublish_items", str(unpublish_items),
            "--tenant_id", env_credentials.get("tenant_id"),
            "--client_id", env_credentials.get("client_id"),
            "--client_secret", env_credentials.get("client_secret")
            ]

    process = subprocess.Popen(['python', '-u', script_path] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')

    # Print output live
    for line in process.stdout:
        print(line, end='')

    # Wait for the process to complete and get the exit code
    process.wait()