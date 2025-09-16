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
parser.add_argument("--tenant_id", required=False, default=os.environ.get('TENANT_ID'), help="Azure Active Directory (Microsoft Entra ID) tenant ID used for authenticating with Fabric APIs. Defaults to the TENANT_ID environment variable.")
parser.add_argument("--client_id", required=False, default=os.environ.get('CLIENT_ID'), help="Client ID of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_ID environment variable.")
parser.add_argument("--client_secret", required=False, default=os.environ.get('CLIENT_SECRET'), help="Client secret of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_SECRET environment variable.")

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
workspace_name_escaped = workspace_name.replace("/", "\\/")
sqldb_item = fabcli.get_item(f"/{workspace_name_escaped}.Workspace/{database}.SQLDatabase")

# Example: You may want to adjust the server/database names per environment
server = sqldb_item.get('properties').get('serverFqdn')
database = sqldb_item.get("properties").get("databaseName")

connection_string = (
    f"Server={server};"
    f"Database={database};"
    f"Authentication=Active Directory Service Principal;"
    f"User Id={client_id};"
    f"Password={client_secret};"
    f"Encrypt=True;"
    f"Connection Timeout=60;"
)

with open(args.output_file, "w") as f:
    f.write(connection_string)