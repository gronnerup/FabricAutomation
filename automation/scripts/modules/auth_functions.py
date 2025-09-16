from azure.identity import InteractiveBrowserCredential
from azure.core.credentials import AccessToken, TokenCredential
import requests, time, json, os, jwt

def get_credentials_from_file(file_name):
    """
    Loads credentials from a specified JSON file located in the same directory as the script.

    Args:
        file_name (str): The name of the JSON file containing the credentials.

    Returns:
        dict: A dictionary containing the credentials as key-value pairs.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, file_name)

    with open(file_path, "r") as file:
        return json.load(file)

def get_environment_credentials(environment: str, folder_path: str):
    """
    Retrieves credentials for the specified environment from a JSON file.

    Args:
        environment (str): The name of the environment (e.g., "dev", "test", "prod").
        folder_path (str): The base folder path where credential files are stored.

    Returns:
        dict or None: A dictionary containing the credentials if found, otherwise None.
    """
    
    if os.path.exists(os.path.join(os.path.dirname(__file__), f'../../credentials/credentials.{environment}.json')):
        credentials = get_credentials_from_file(os.path.join(os.path.dirname(__file__), f'../../credentials/credentials.{environment}.json'))
    elif os.path.exists(os.path.join(os.path.dirname(__file__), f'../../credentials/credentials.json')):
        credentials = get_credentials_from_file(os.path.join(os.path.dirname(__file__), f'../../credentials/credentials.json')) 
    else:
        credentials = None
        
    return credentials

def create_credentials_from_user():
    """
    Creates a ResourceManagementClient instance for Azure resources using 
    InteractiveBrowserCredential for authentication.
    """
    return InteractiveBrowserCredential()


def get_access_token_from_credentials(credential : InteractiveBrowserCredential, resource):
    """
    Creates a ResourceManagementClient instance for Azure resources using 
    InteractiveBrowserCredential for authentication.

    Args:
        credential (InteractiveBrowserCredential): The credential object for the authenticated user.
        resource (str): The URI of the resource for which the access token is requested, e.g., "https://management.azure.com/" for Azure Management APIs.

    Returns:
        ResourceManagementClient: A client instance used to authenticate and manage Azure resources.
    """
    return credential.get_token(resource).token


def get_access_token(tenant_id, client_id, client_secret, resource):
    """
    Obtains an OAuth 2.0 access token for authenticating with Azure, Power BI, or Fabric services.

    Args:
        tenant_id (str): The Azure AD tenant ID where the application is registered.
        client_id (str): The client (application) ID of the registered Azure AD application.
        client_secret (str): The client secret of the registered Azure AD application.
        resource (str): The URI of the resource for which the access token is requested, e.g., "https://management.azure.com/" for Azure Management APIs.

    Returns:
        str: The access token string used to authenticate requests to the specified resource.
    """
    request_access_token_uri = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'resource': resource
    }

    response = requests.post(request_access_token_uri, data=payload,headers={'Content-Type': 'application/x-www-form-urlencoded'})    
    response.raise_for_status()

    return response.json().get('access_token')


def is_service_principal(token):
    """
    Determines whether the given token belongs to a service principal.

    This function decodes the JWT token without verifying the signature 
    and checks the "idtyp" (identity type) claim. If the claim is "User", 
    the token represents a user; otherwise, it is assumed to be a service principal.

    Args:
        token (str): The JWT token to inspect.

    Returns:
        bool: True if the token belongs to a service principal, False if it belongs to a user.
    """
    decoded = jwt.decode(token, options={"verify_signature": False})
    
    if decoded.get("idtyp", "") == "User":
        return False
    else:
        return True
    

class StaticTokenCredential(TokenCredential):
    def __init__(self, access_token: str, expires_on: int = None):
        self.aad_token = access_token
        self.aad_token_expiration = expires_on or int(time.time()) + 3600

    def get_token(self, *scopes) -> AccessToken:
        return AccessToken(self.aad_token, self.aad_token_expiration)