import os, sys, io, argparse, time
import modules.fabric_cli_functions as fabcli
import modules.misc_functions as misc

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdout.reconfigure(line_buffering=True)

# Get arguments
parser = argparse.ArgumentParser(description="Fabric IaC setup arguments")
parser.add_argument("--environment", required=True, help="Name of environment to generate connection string for.")
parser.add_argument("--layer", required=True, help="Name of layer to generate connection string for.")
parser.add_argument("--database", required=True, help="Name of database to generate connection string for.")
parser.add_argument('--output_file', required=True, help="Path to output file where the connection string will be saved.")
parser.add_argument("--tenant_id", required=False, default=os.environ.get('FAB_TENANT_ID'), help="Azure Active Directory (Microsoft Entra ID) tenant ID used for authenticating with Fabric APIs. Defaults to the TENANT_ID environment variable.")
parser.add_argument("--client_id", required=False, default=os.environ.get('FAB_SPN_CLIENT_ID'), help="Client ID of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_ID environment variable.")
parser.add_argument("--client_secret", required=False, default=os.environ.get('FAB_SPN_CLIENT_SECRET'), help="Client secret of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_SECRET environment variable.")

args = parser.parse_args()
environment = args.environment
layer = args.layer
database = args.database    
tenant_id = args.tenant_id
client_id = args.client_id
client_secret = args.client_secret
output_file = args.output_file

# Authenticate
fabcli.run_command("config set encryption_fallback_enabled true")
fabcli.run_command(f"auth login -u {client_id} -p {client_secret} --tenant {tenant_id}")

# Load JSON environment files (main and environment specific) and merge
main_json = misc.load_json(os.path.join(os.path.dirname(__file__), f'../resources/environments/infrastructure.json'))
env_json = misc.load_json(os.path.join(os.path.dirname(__file__), f'../resources/environments/infrastructure.{environment}.json'))
env_definition = misc.merge_json(main_json, env_json)

solution_name = env_definition.get("name")
workspace_name = solution_name.format(layer=layer, environment=environment)

item_type = None
for env_item_type in env_definition.get("layers").get(layer).get("items"):
    if env_item_type in ["Warehouse","SQLDatabase"]:
        for item in env_definition.get("layers").get(layer).get("items").get(env_item_type):
            item_name = item.get("item_name")
            if item_name == database:
                item_type = env_item_type
                break 

connection_string = fabcli.generate_connection_string(
    workspace_name=workspace_name,
    item_type=item_type,
    database=database,
    client_id=client_id,
    client_secret=client_secret
)

with open(args.output_file, "w") as f:
    f.write(connection_string)